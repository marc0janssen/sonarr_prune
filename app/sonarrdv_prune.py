# Name: Sonarr Prune
# Coder: Marco Janssen (mastodon @marc0janssen@mastodon.green)
# date: 2023-12-31 19:38:00
# update: 2024-03-09 22:14:00

import logging
import configparser
import sys
import shutil
import smtplib
import os
import requests
import psutil
import time

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from arrapi import SonarrAPI, exceptions
from chump import Application
from socket import gaierror


class SONARRPRUNE():

    def __init__(self, config_path=None):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO)

        config_dir = "/config/"
        app_dir = "/app/"
        log_dir = "/var/log/"

        self.config_file = "sonarrdv_prune.ini"
        self.exampleconfigfile = "sonarrdv_prune.ini.example"
        self.log_file = "sonarr_prune.log"
        self.firstcomplete = ".firstcomplete"

        # Allow overriding the config file path (useful for tests)
        if config_path:
            self.config_filePath = config_path
        else:
            self.config_filePath = f"{config_dir}{self.config_file}"
        self.log_filePath = f"{log_dir}{self.log_file}"

        try:
            with open(self.config_filePath, "r") as f:
                f.close()
            try:
                self.config = configparser.ConfigParser()
                self.config.read(self.config_filePath)

                # SONARR
                # Use ConfigParser helpers with safe fallbacks
                # and normalize lists where appropriate
                self.sonarrdv_enabled = self.config.getboolean(
                    'SONARRDV', 'ENABLED', fallback=False
                )
                self.sonarrdv_url = self.config.get(
                    'SONARRDV', 'URL', fallback=''
                )
                self.sonarrdv_token = self.config.get(
                    'SONARRDV', 'TOKEN', fallback=''
                )

                def _cfg_boolean(section, option, fallback=False):
                    """Robust boolean parser that accepts ON/OFF as well as
                    true/false/1/0. ConfigParser.getboolean already supports
                    these, but some edge cases (malformed values) are handled
                    gracefully here.
                    """
                    try:
                        return self.config.getboolean(
                            section, option, fallback=fallback
                        )
                    except Exception:
                        raw = self.config.get(section, option, fallback=None)
                        if raw is None:
                            return fallback
                        v = str(raw).strip().lower()
                        return v in ("1", "true", "yes", "on")

                # EMBY1
                self.emby_enabled1 = _cfg_boolean('EMBY1', 'ENABLED', False)
                self.emby_url1 = self.config.get(
                    'EMBY1', 'URL', fallback=''
                )
                self.emby_token1 = self.config.get(
                    'EMBY1', 'TOKEN', fallback=''
                )

                # EMBY2
                self.emby_enabled2 = _cfg_boolean('EMBY2', 'ENABLED', False)
                self.emby_url2 = self.config.get(
                    'EMBY2', 'URL', fallback=''
                )
                self.emby_token2 = self.config.get(
                    'EMBY2', 'TOKEN', fallback=''
                )

                # PRUNE
                self.remove_after_days = self.config.getint(
                    'PRUNE', 'REMOVE_SERIES_AFTER_DAYS', fallback=30
                )
                self.remove_percentage = self.config.getfloat(
                    'PRUNE', 'REMOVE_SERIES_DISK_PERCENTAGE', fallback=90.0
                )
                self.warn_days_infront = self.config.getint(
                    'PRUNE', 'WARN_DAYS_INFRONT', fallback=1
                )
                self.dry_run = _cfg_boolean('PRUNE', 'DRY_RUN', False)
                # split and strip tags, ignore empty
                raw_tags = self.config.get(
                    'PRUNE', 'TAGS_KEEP_MOVIES_ANYWAY', fallback=''
                )
                self.tags_to_keep = [
                    t.strip() for t in raw_tags.split(',') if t.strip()
                ]
                self.enabled_run = _cfg_boolean('PRUNE', 'ENABLED', True)
                self.only_show_remove_messages = _cfg_boolean(
                    'PRUNE', 'ONLY_SHOW_REMOVE_MESSAGES', False
                )
                self.verbose_logging = _cfg_boolean(
                    'PRUNE', 'VERBOSE_LOGGING', False
                )
                self.mail_enabled = _cfg_boolean(
                    'PRUNE', 'MAIL_ENABLED', False
                )
                self.only_mail_when_removed = _cfg_boolean(
                    'PRUNE', 'ONLY_MAIL_WHEN_REMOVED', False
                )
                self.mail_port = self.config.getint(
                    'PRUNE', 'MAIL_PORT', fallback=587
                )
                self.mail_server = self.config.get(
                    'PRUNE', 'MAIL_SERVER', fallback=''
                )
                self.mail_login = self.config.get(
                    'PRUNE', 'MAIL_LOGIN', fallback=''
                )
                self.mail_password = self.config.get(
                    'PRUNE', 'MAIL_PASSWORD', fallback=''
                )
                self.mail_sender = self.config.get(
                    'PRUNE', 'MAIL_SENDER', fallback=''
                )
                raw_receivers = self.config.get(
                    'PRUNE', 'MAIL_RECEIVER', fallback=''
                )
                self.mail_receiver = [
                    r.strip() for r in raw_receivers.split(',') if r.strip()
                ]

                # PUSHOVER
                self.pushover_enabled = _cfg_boolean(
                    'PUSHOVER', 'ENABLED', False
                )
                self.pushover_user_key = self.config.get(
                    'PUSHOVER', 'USER_KEY', fallback=''
                )
                self.pushover_token_api = self.config.get(
                    'PUSHOVER', 'TOKEN_API', fallback=''
                )
                self.pushover_sound = self.config.get(
                    'PUSHOVER', 'SOUND', fallback=''
                )

            except KeyError as e:
                logging.error(
                    f"Seems a key(s) {e} is missing from INI file. "
                    f"Please check for mistakes. Exiting."
                )

                sys.exit()

            except ValueError as e:
                logging.error(
                    f"Seems a invalid value in INI file. "
                    f"Please check for mistakes. Exiting. "
                    f"MSG: {e}"
                )

                sys.exit()

        except (IOError, FileNotFoundError):
            logging.error(
                f"Can't open file {self.config_filePath}, "
                f"creating example INI file."
            )

            shutil.copyfile(f'{app_dir}{self.exampleconfigfile}',
                            f'{config_dir}{self.exampleconfigfile}')
            sys.exit()

    def isDiskFull(self):
        # Get the Rootfolers and diskage
        if not self.sonarrdv_enabled:
            return False, 0.0

        try:
            folders = self.sonarrNode.root_folder()
            if not folders:
                return False, 0.0
            root_Folder = folders[0]
            diskInfo = psutil.disk_usage(root_Folder.path)
            isFull = diskInfo.percent >= self.remove_percentage
            return (isFull, diskInfo.percent)
        except Exception as e:
            logging.error(f"Failed to determine disk usage: {e}")
            return False, 0.0

    def trigger_database_update_emby1(self):

        headers = {}
        data = {}

        url = \
            f"{self.emby_url1}/Emby/Library/Refresh?api_key={self.emby_token1}"
        response = requests.post(url, data=data, headers=headers)

        if response.status_code == 204:
            logging.info(
                "Database update triggered successfully for Emby1.")
        else:
            logging.error(
                f"Failed to trigger database update for Emby1. Status code: "
                f"{response.status_code}")

    def trigger_database_update_emby2(self):

        headers = {}
        data = {}

        url = \
            f"{self.emby_url2}/Emby/Library/Refresh?api_key={self.emby_token2}"
        response = requests.post(url, data=data, headers=headers)

        if response.status_code == 204:
            logging.info(
                "Database update triggered successfully for Emby2.")
        else:
            logging.error(
                f"Failed to trigger database update for Emby2. Status code: "
                f"{response.status_code}")

    # Trigger a database update in Sonarr
    def trigger_database_update_sonarr(self):
        headers = {
            'X-Api-Key': self.sonarrdv_token,
            'Content-Type': 'application/json'
            }
        payload = {'name': 'refreshseries'}
        endpoint = "/api/v3/command"

        if self.sonarrdv_enabled:
            response = requests.post(
                self.sonarrdv_url + endpoint, json=payload, headers=headers)

            if response.status_code == 201:
                logging.info(
                    "Database update triggered successfully for Sonarr (DV).")
            else:
                logging.error(
                    f"Failed to trigger database update for Sonarr (DV). "
                    f"Status code: {response.status_code}"
                    )

    def writeLog(self, init, msg):

        try:
            if init:
                logfile = open(self.log_filePath, "w")
            else:
                logfile = open(self.log_filePath, "a")
            logfile.write(f"{datetime.now()} - {msg}")
            logfile.close()
        except IOError:
            logging.error(
                f"Can't write file {self.log_filePath}."
            )

    def sortOnTitle(self, e):
        return e.sortTitle

    def getTagLabeltoID(self):
        # Put all tags in a dictonairy with pair label <=> ID

        TagLabeltoID = {}
        for tag in self.sonarrNode.all_tags():
            # Add tag to lookup by it's name
            TagLabeltoID[tag.label] = tag.id

        return TagLabeltoID

    def getIDsforTagLabels(self, tagLabels):

        TagLabeltoID = self.getTagLabeltoID()

        # Get ID's for extending media
        tagsIDs = []
        for taglabel in tagLabels:
            tagID = TagLabeltoID.get(taglabel)
            if tagID:
                tagsIDs.append(tagID)

        return tagsIDs

    def evalSeason(self, serie, season):

        isRemoved, isPlanned = False, False
        seasonDownloadDate = None

        seasonDir = "Specials" if season.seasonNumber == 0 \
            else f"Season {season.seasonNumber}"

        if os.path.exists(f"{serie.path}/{seasonDir}"):

            if season.totalEpisodeCount == season.episodeFileCount:

                if not os.path.isfile(
                        f"{serie.path}/{seasonDir}/{self.firstcomplete}"):

                    with open(
                        f"{serie.path}/{seasonDir}/{self.firstcomplete}",
                            'w') \
                            as firstcomplete_file:
                        firstcomplete_file.close()

                        if not self.only_show_remove_messages:
                            txtFirstSeen = (
                                f"PRUNE: COMPLETE - {serie.title} "
                                f"S{str(season.seasonNumber)} ({serie.year})"
                            )

                            self.writeLog(False, f"{txtFirstSeen}\n")
                            logging.info(txtFirstSeen)

                modifieddate = os.stat(
                    f"{serie.path}/{seasonDir}/"
                    f"{self.firstcomplete}").st_mtime

                seasonDownloadDate = \
                    datetime.fromtimestamp(modifieddate)

            now = datetime.now()

            if seasonDownloadDate:

                # check if there needs to be warn "DAYS" infront of removal
                # 1. Are we still within the period before removel?
                # 2. Is "NOW" less than "warning days" before removal?
                # 3. is "NOW" more then "warning days - 1" before removal
                #               (warn only 1 day)

                isFull, percentage = self.isDiskFull()

                if (
                    timedelta(
                        days=self.remove_after_days) >
                    now - seasonDownloadDate and
                    seasonDownloadDate +
                    timedelta(
                        days=self.remove_after_days) -
                    now <= timedelta(days=self.warn_days_infront) and
                    seasonDownloadDate +
                    timedelta(
                        days=self.remove_after_days) -
                    now > timedelta(days=self.warn_days_infront) -
                    timedelta(days=1)
                ):
                    self.timeLeft = (
                        seasonDownloadDate +
                        timedelta(
                            days=self.remove_after_days) - now)

                    txtTimeLeft = \
                        'h'.join(str(self.timeLeft).split(':')[:2])

                    if self.pushover_enabled:
                        self.message = self.userPushover.send_message(
                            message=f"Prune - {serie.title} "
                            f"Season {str(season.seasonNumber).zfill(2)}"
                            f" ({serie.year}) "
                            f"will be removed from server in "
                            f"{txtTimeLeft}",
                            sound=self.pushover_sound
                        )

                    txtWillBeRemoved = (
                        f"PRUNE: WARNING - {serie.title} "
                        f"Season {str(season.seasonNumber).zfill(2)} "
                        f"({serie.year}) will be removed in {txtTimeLeft}."
                    )

                    self.writeLog(False, f"{txtWillBeRemoved}\n")
                    logging.info(txtWillBeRemoved)

                    # report current disk usage and threshold
                    self.writeLog(
                        False,
                        f"Disk usage: {percentage}% "
                        f"(threshold: {self.remove_percentage}%)\n",
                    )
                    logging.info(
                        f"Disk usage: {percentage}% "
                        f"(threshold: {self.remove_percentage}%)"
                    )

                    isRemoved, isPlanned = False, True

                    return isRemoved, isPlanned

                # Check is season is older than "days set in INI"

                if (
                    now - seasonDownloadDate >=
                        timedelta(
                            days=self.remove_after_days) and isFull
                ):

                    if not self.dry_run:
                        if self.sonarrdv_enabled:

                            try:
                                # Delete Season
                                shutil.rmtree(f"{serie.path}/{seasonDir}")

                            except FileNotFoundError:
                                logging.error(
                                    f"Season Not Found {serie.title} "
                                    f"season {season.seasonNumber}"
                                    )
                            except OSError as error:
                                logging.error(
                                    f"Error removing {serie.title} "
                                    f"season {season.seasonNumber}: {error}"
                                    )

                    txtTitle = (
                        f"{serie.title} ({serie.year}) - "
                        f"Season {str(season.seasonNumber).zfill(2)}"
                    )

                    if self.pushover_enabled:
                        self.message = self.userPushover.send_message(
                            message=(
                                f"PRUNE: REMOVED - {txtTitle} "
                                f"(removed: {seasonDownloadDate})"
                            ),
                            sound=self.pushover_sound,
                        )

                    txtRemoved = (
                        f"PRUNE: REMOVED - {txtTitle} "
                        f"(removed: {seasonDownloadDate})"
                    )

                    self.writeLog(False, f"{txtRemoved}\n")
                    logging.info(txtRemoved)

                    self.writeLog(
                        False,
                        f"Disk usage: {percentage}% "
                        f"(threshold: {self.remove_percentage}%)\n",
                    )
                    logging.info(
                        f"Disk usage: {percentage}% "
                        f"(threshold: {self.remove_percentage}%)"
                    )

                    isRemoved, isPlanned = True, False

                else:
                    if not self.only_show_remove_messages:

                        txtActive = (
                            f"PRUNE: ACTIVE - {serie.title} "
                            f"Season {str(season.seasonNumber).zfill(2)} "
                            f"({serie.year}) - first complete: "
                            f"{seasonDownloadDate}"
                        )

                        self.writeLog(False, f"{txtActive}\n")
                        logging.info(txtActive)

                    isRemoved, isPlanned = False, False

        return isRemoved, isPlanned

    def run(self):
        if not self.enabled_run:
            logging.info(
                "Prune - Library purge disabled.")
            self.writeLog(False, "Prune - Library purge disabled.\n")
            sys.exit()

        # Connect to Sonarr DV
        if self.sonarrdv_enabled:
            try:
                self.sonarrNode = SonarrAPI(
                    self.sonarrdv_url, self.sonarrdv_token)
            except exceptions.ArrException as e:
                logging.error(
                    f"Can't connect to Sonarr source {e}"
                )
                sys.exit()
            except Exception as e:
                logging.error(
                    f"Unexpected error connecting Sonarr source: {e}")
                sys.exit(1)
        else:
            logging.info(
                "Prune - Sonarr DV disabled in INI, exiting.")
            self.writeLog(False, "Sonarr disabled in INI, exiting.\n")
            sys.exit()

        if self.dry_run:
            logging.info(
                "*****************************************************")
            logging.info(
                "**** DRY RUN, NOTHING WILL BE DELETED OR REMOVED ****")
            logging.info(
                "*****************************************************")
            self.writeLog(False, "Dry Run.\n")

        # Setting for PushOver
        if self.pushover_enabled:
            self.appPushover = Application(self.pushover_token_api)
            self.userPushover = \
                self.appPushover.get_user(self.pushover_user_key)

        # Get all Series from the server.
        media = None
        if self.sonarrdv_enabled:
            media = self.sonarrNode.all_series()

        if self.verbose_logging:
            logging.info("Prune - Sonarr Prune started.")
        self.writeLog(True, "Prune - Sonarr Prune started.\n")

        # Make sure the library is not empty.
        numDeleted = 0
        numNotified = 0
        isRemoved, isPlanned = False, False

        isFull, percentage = self.isDiskFull()

        logging.info(f"Percentage diskspace sonarrdv: {percentage}%")

        if media and isFull:
            media.sort(key=self.sortOnTitle)  # Sort the list on Title
            for serie in media:

                # Get ID's for keeping series anyway
                tagLabels_to_keep = self.tags_to_keep
                tagsIDs_to_keep = self.getIDsforTagLabels(
                    tagLabels_to_keep)

                # check if ONE of the "KEEP" tags is
                # in the set of "MOVIE TAGS"
                if set(serie.tagsIds) & set(tagsIDs_to_keep):
                    if not self.only_show_remove_messages:

                        txtKeeping = (
                            f"Prune - KEEPING - {serie.title} ({serie.year})."
                            f" Skipping."
                        )

                        self.writeLog(False, f"{txtKeeping}\n")
                        logging.info(txtKeeping)

                else:

                    seasons = serie.seasons

                    subNumDeleted = 0
                    subNumNotified = 0

                    for season in seasons:

                        isRemoved, isPlanned = \
                            self.evalSeason(serie, season)
                        if isRemoved:
                            subNumDeleted += 1
                        if isPlanned:
                            subNumNotified += 1

                    numDeleted += subNumDeleted
                    numNotified += subNumNotified

                time.sleep(0.2)

        txtEnd = (
            f"Prune - There were {numDeleted} seasons removed."
        )

        if self.pushover_enabled:
            self.message = self.userPushover.send_message(
                message=txtEnd,
                sound=self.pushover_sound
            )

        if self.verbose_logging:
            logging.info(txtEnd)
            logging.info(f"Percentage diskspace sonarrdv: {percentage}%")
        self.writeLog(False, f"{txtEnd}\n")
        self.writeLog(False, f"Percentage diskspace sonarrdv: {percentage}%\n")

        if self.mail_enabled and \
            (not self.only_mail_when_removed or
                (self.only_mail_when_removed and (
                    numDeleted > 0 or numNotified > 0))):

            sender_email = self.mail_sender
            receiver_email = self.mail_receiver

            message = MIMEMultipart()
            message["From"] = sender_email
            message['To'] = ", ".join(receiver_email)
            message['Subject'] = (
                f"Sonarr - Pruned {numDeleted} seasons "
                f"and {numNotified} planned for removal"
            )

            attachment = open(self.log_filePath, 'rb')
            obj = MIMEBase('application', 'octet-stream')
            obj.set_payload((attachment).read())
            encoders.encode_base64(obj)
            obj.add_header(
                'Content-Disposition',
                "attachment; filename= "+self.log_file
            )
            message.attach(obj)

            body = (
                "Hi,\n\n Attached is the prunelog from sonarr Prune.\n\n"
                "Have a nice day.\n\n"
            )

            logfile = open(self.log_filePath, "r")

            body += ''.join(logfile.readlines())

            logfile.close()

            plain_text = MIMEText(
                body, _subtype='plain', _charset='UTF-8')
            message.attach(plain_text)

            my_message = message.as_string()

            try:
                email_session = smtplib.SMTP(
                    self.mail_server, self.mail_port)
                email_session.starttls()
                email_session.login(
                    self.mail_login, self.mail_password)
                email_session.sendmail(
                    self.mail_sender, self.mail_receiver, my_message)
                email_session.quit()
                logging.info(f"Prune - Mail Sent to {message['To']}.")
                self.writeLog(
                    False, f"Prune - Mail Sent to {message['To']}.\n")

            except (gaierror, ConnectionRefusedError):
                logging.error(
                    "Failed to connect to the server. "
                    "Bad connection settings?")
            except smtplib.SMTPServerDisconnected:
                logging.error(
                    "Failed to connect to the server. "
                    "Wrong user/password?"
                )
            except smtplib.SMTPException as e:
                logging.error(
                    "SMTP error occurred: " + str(e))

        # Call the function to trigger a database update

        if self.sonarrdv_enabled:
            self.trigger_database_update_sonarr()

        if self.emby_enabled1:
            self.trigger_database_update_emby1()

        if self.emby_enabled2:
            self.trigger_database_update_emby2()


if __name__ == '__main__':

    sonarrprune = SONARRPRUNE()
    sonarrprune.run()
    sonarrprune = None
