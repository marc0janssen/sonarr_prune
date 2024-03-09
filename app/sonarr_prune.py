# Name: Sonarr Prune
# Coder: Marco Janssen (mastodon @marc0janssen@mastodon.online)
# date: 2023-12-31 19:38:00
# update: 2024-03-09 22:14:00

import logging
import configparser
import sys
import shutil
import smtplib
import os
import requests

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from arrapi import SonarrAPI
from chump import Application
from socket import gaierror


class SONARRPRUNE():

    def __init__(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO)

        config_dir = "/config/"
        app_dir = "/app/"
        log_dir = "/logging/"

        self.config_file = "sonarr_prune.ini"
        self.exampleconfigfile = "sonarr_prune.ini.example"
        self.log_file = "sonarr_prune.log"
        self.firstcomplete = ".firstcomplete"

        self.config_filePath = f"{config_dir}{self.config_file}"
        self.log_filePath = f"{log_dir}{self.log_file}"

        try:
            with open(self.config_filePath, "r") as f:
                f.close()
            try:
                self.config = configparser.ConfigParser()
                self.config.read(self.config_filePath)

                # SONARR
                self.sonarrhd_enabled = True if (
                    self.config['SONARRHD']['ENABLED'] == "ON") else False
                self.sonarrhd_url = self.config['SONARRHD']['URL']
                self.sonarrhd_token = self.config['SONARRHD']['TOKEN']

                # SONARR2
                self.sonarrdv_enabled = True if (
                    self.config['SONARRDV']['ENABLED'] == "ON") else False
                self.sonarrdv_url = self.config['SONARRDV']['URL']
                self.sonarrdv_token = self.config['SONARRDV']['TOKEN']

                # EMBY
                self.emby_enabled = True if (
                    self.config['EMBY']['ENABLED'] == "ON") else False
                self.emby_url = self.config['EMBY']['URL']
                self.emby_token = self.config['EMBY']['TOKEN']

                # PRUNE
                # list(map(int, "list")) converts a list of string to
                # a list of ints
                self.remove_after_days = int(
                    self.config['PRUNE']['REMOVE_SERIES_AFTER_DAYS'])
                self.warn_days_infront = int(
                    self.config['PRUNE']['WARN_DAYS_INFRONT'])
                self.dry_run = True if (
                    self.config['PRUNE']['DRY_RUN'] == "ON") else False
                self.tags_to_keep = list(
                    self.config['PRUNE']
                    ['TAGS_KEEP_MOVIES_ANYWAY'].split(",")
                )
                self.enabled_run = True if (
                    self.config['PRUNE']['ENABLED'] == "ON") else False
                self.only_show_remove_messages = True if (
                    self.config['PRUNE']
                    ['ONLY_SHOW_REMOVE_MESSAGES'] == "ON") else False
                self.verbose_logging = True if (
                    self.config['PRUNE']['VERBOSE_LOGGING'] == "ON") else False
                self.mail_enabled = True if (
                    self.config['PRUNE']
                    ['MAIL_ENABLED'] == "ON") else False
                self.only_mail_when_removed = True if (
                    self.config['PRUNE']
                    ['ONLY_MAIL_WHEN_REMOVED'] == "ON") else False
                self.mail_port = int(
                    self.config['PRUNE']['MAIL_PORT'])
                self.mail_server = self.config['PRUNE']['MAIL_SERVER']
                self.mail_login = self.config['PRUNE']['MAIL_LOGIN']
                self.mail_password = self.config['PRUNE']['MAIL_PASSWORD']
                self.mail_sender = self.config['PRUNE']['MAIL_SENDER']
                self.mail_receiver = list(
                    self.config['PRUNE']['MAIL_RECEIVER'].split(","))

                # PUSHOVER
                self.pushover_enabled = True if (
                    self.config['PUSHOVER']['ENABLED'] == "ON") else False
                self.pushover_user_key = self.config['PUSHOVER']['USER_KEY']
                self.pushover_token_api = self.config['PUSHOVER']['TOKEN_API']
                self.pushover_sound = self.config['PUSHOVER']['SOUND']

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

        except IOError or FileNotFoundError:
            logging.error(
                f"Can't open file {self.config_filePath}, "
                f"creating example INI file."
            )

            shutil.copyfile(f'{app_dir}{self.exampleconfigfile}',
                            f'{config_dir}{self.exampleconfigfile}')
            sys.exit()

    def trigger_database_update_emby(self):

        headers = {}
        data = {}
        url = f"{self.emby_url}/Emby/Library/Refresh?api_key={self.emby_token}"

        response = requests.post(url, data, headers)

        if response.status_code == 204:
            logging.info(
                "Database update triggered successfully for Emby.")
        else:
            logging.error(
                f"Failed to trigger database update for Emby. Status code: "
                f"{response.status_code}")

    # Trigger a database update in Sonarr
    def trigger_database_update_sonarr(self):
        headers = {
            'X-Api-Key': self.sonarrhd_token,
            'Content-Type': 'application/json'
            }
        payload = {'name': 'refreshseries'}
        endpoint = "/api/v3/command"

        if self.sonarrhd_enabled:
            response = requests.post(
                self.sonarrhd_url + endpoint, json=payload, headers=headers)

            if response.status_code == 201:
                logging.info(
                    "Database update triggered successfully for Sonarr (HD).")
            else:
                logging.error(
                    f"Failed to trigger database update for Sonarr (HD). "
                    f"Status code: {response.status_code}"
                    )

        headers = {
            'X-Api-Key': self.sonarrdv_token,
            'Content-Type': 'application/json'
            }

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

    def getTagLabeltoID(self, typeOfMedia):
        # Put all tags in a dictonairy with pair label <=> ID

        TagLabeltoID = {}
        if typeOfMedia == "serie":
            for tag in self.sonarrNode.all_tags():
                # Add tag to lookup by it's name
                TagLabeltoID[tag.label] = tag.id
        else:
            for tag in self.radarrNode.all_tags():
                # Add tag to lookup by it's name
                TagLabeltoID[tag.label] = tag.id

        return TagLabeltoID

    def getIDsforTagLabels(self, typeOfmedia, tagLabels):

        TagLabeltoID = self.getTagLabeltoID(typeOfmedia)

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

        if season.totalEpisodeCount == season.episodeCount:

            if not os.path.isfile(
                    f"{serie.path}/{seasonDir}/{self.firstcomplete}"):

                with open(
                    f"{serie.path}/{seasonDir}/{self.firstcomplete}", 'w') \
                        as firstcomplete_file:
                    firstcomplete_file.close()

                    if not self.only_show_remove_messages:
                        txtFirstSeen = (
                            f"Prune - COMPLETE - "
                            f"{serie.title} S"
                            f"{str(season.seasonNumber)} "
                            f"({serie.year})"
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
                    f"Prune - WILL BE REMOVED - "
                    f"{serie.title} "
                    f"Season {str(season.seasonNumber).zfill(2)}"
                    f" ({serie.year})"
                    f" in {txtTimeLeft}"
                    f" - {seasonDownloadDate}"
                )

                self.writeLog(False, f"{txtWillBeRemoved}\n")
                logging.info(txtWillBeRemoved)

                isRemoved, isPlanned = False, True

                return isRemoved, isPlanned

            # Check is season is older than "days set in INI"
            if (
                now - seasonDownloadDate >=
                    timedelta(
                        days=self.remove_after_days)
            ):

                if not self.dry_run:
                    if self.sonarrhd_enabled:

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

                        if self.sonarrdv_enabled:
                            try:
                                # Delete Season
                                seriesdvPath = serie.path.replace(
                                    "/content/video/series",
                                    "/content/video/seriesdv"
                                    )

                                shutil.rmtree(f"{seriesdvPath}/{seasonDir}")

                            except FileNotFoundError:
                                pass

                            except OSError as error:
                                logging.error(
                                    f"Error removing DV {serie.title} "
                                    f"season {season.seasonNumber}: {error}"
                                    )

                if self.pushover_enabled:
                    self.message = self.userPushover.send_message(
                        message=f"{serie.title} "
                        f"Season {str(season.seasonNumber).zfill(2)} "
                        f"({serie.year})"
                        f"Prune - REMOVED - {serie.title} "
                        f"Season {str(season.seasonNumber).zfill(2)} "
                        f"({serie.year})"
                        f" - {seasonDownloadDate}",
                        sound=self.pushover_sound
                    )

                txtRemoved = (
                    f"Prune - REMOVED - {serie.title} "
                    f"Season {str(season.seasonNumber).zfill(2)} "
                    f"({serie.year})"
                    f" - {seasonDownloadDate}"
                )

                self.writeLog(False, f"{txtRemoved}\n")
                logging.info(txtRemoved)

                isRemoved, isPlanned = True, False

            else:
                if not self.only_show_remove_messages:
                    txtActive = (
                        f"Prune - ACTIVE - "
                        f"{serie.title} "
                        f"Season {str(season.seasonNumber).zfill(2)} "
                        f"({serie.year})"
                        f" - {seasonDownloadDate}"
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

        # Connect to Sonarr HD
        if self.sonarrhd_enabled:
            self.sonarrNode = SonarrAPI(
                self.sonarrhd_url, self.sonarrhd_token)
        else:
            logging.info(
                "Prune - Sonarr HD disabled in INI, exting.")
            self.writeLog(False, "Sonarr disabled in INI, exting.\n")
            sys.exit()

        # Connect to Sonarr DV
        if self.sonarrdv_enabled:
            self.sonarrNode1 = SonarrAPI(
                self.sonarrdv_url, self.sonarrdv_token)
        else:
            logging.info(
                "Prune - Sonarr DV disabled in INI, exting.")
            self.writeLog(False, "Sonarr disabled in INI, exting.\n")

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
        if self.sonarrhd_enabled:
            media = self.sonarrNode.all_series()

        if self.verbose_logging:
            logging.info("Prune - Sonarr Prune started.")
        self.writeLog(True, "Prune - Sonarr Prune started.\n")

        # Make sure the library is not empty.
        numDeleted = 0
        numNotifified = 0
        isRemoved, isPlanned = False, False
        if media:
            media.sort(key=self.sortOnTitle)  # Sort the list on Title
            for serie in media:

                # Get ID's for keeping series anyway
                tagLabels_to_keep = self.tags_to_keep
                tagsIDs_to_keep = self.getIDsforTagLabels(
                    "serie", tagLabels_to_keep)

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
                    subNnumNotifified = 0

                    for season in seasons:

                        isRemoved, isPlanned = \
                            self.evalSeason(serie, season)
                        if isRemoved:
                            subNumDeleted += 1
                        if isPlanned:
                            subNnumNotifified += 1

                    numDeleted += subNumDeleted
                    numNotifified += subNnumNotifified

        txtEnd = (
            f"Prune - There were {numDeleted} seaons removed."
        )

        if self.pushover_enabled:
            self.message = self.userPushover.send_message(
                message=txtEnd,
                sound=self.pushover_sound
            )

        if self.verbose_logging:
            logging.info(txtEnd)
        self.writeLog(False, f"{txtEnd}\n")

        if self.mail_enabled and \
            (not self.only_mail_when_removed or
                (self.only_mail_when_removed and (
                    numDeleted > 0 or numNotifified > 0))):

            sender_email = self.mail_sender
            receiver_email = self.mail_receiver

            message = MIMEMultipart()
            message["From"] = sender_email
            message['To'] = ", ".join(receiver_email)
            message['Subject'] = (
                f"Sonarr - Pruned {numDeleted} seasons "
                f"and {numNotifified} planned for removal"
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

        if self.sonarrhd_enabled or self.sonarrdv_enabled:
            self.trigger_database_update_sonarr()

        if self.emby_enabled:
            self.trigger_database_update_emby()


if __name__ == '__main__':

    sonarrprune = SONARRPRUNE()
    sonarrprune.run()
    sonarrprune = None
