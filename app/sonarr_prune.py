# Name: Sonarr Prune
# Coder: Marco Janssen (mastodon @marc0janssen@mastodon.online)
# date: 2021-11-15 21:38:51
# update: 2023-12-04 21:41:15

import logging
import configparser
import sys
import shutil
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime  # , timedelta
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
        self.firstseen = ".firstseen"

        self.config_filePath = f"{config_dir}{self.config_file}"
        self.log_filePath = f"{log_dir}{self.log_file}"

        try:
            with open(self.config_filePath, "r") as f:
                f.close()
            try:
                self.config = configparser.ConfigParser()
                self.config.read(self.config_filePath)

                # SONARR
                self.sonarr_enabled = True if (
                    self.config['SONARR']['ENABLED'] == "ON") else False
                self.sonarr_url = self.config['SONARR']['URL']
                self.sonarr_token = self.config['SONARR']['TOKEN']
                self.tags_to_keep = list(
                    self.config['SONARR']
                    ['TAGS_KEEP_MOVIES_ANYWAY'].split(",")
                )

                # PRUNE
                self.sonarr_tags_no_exclusion = list(
                    self.config['PRUNE']
                    ['AUTO_NO_EXCLUSION_TAGS'].split(","))
                # list(map(int, "list")) converts a list of string to
                # a list of ints
                self.sonarr_months_no_exclusion = list(map(int, list(
                    self.config['PRUNE']
                    ['AUTO_NO_EXCLUSION_MONTHS'].split(","))))
                self.remove_after_days = int(
                    self.config['PRUNE']['REMOVE_MOVIES_AFTER_DAYS'])
                self.warn_days_infront = int(
                    self.config['PRUNE']['WARN_DAYS_INFRONT'])
                self.dry_run = True if (
                    self.config['PRUNE']['DRY_RUN'] == "ON") else False
                self.enabled_run = True if (
                    self.config['PRUNE']['ENABLED'] == "ON") else False
                self.delete_files = True if (
                    self.config['PRUNE']
                    ['PERMANENT_DELETE_MEDIA'] == "ON") else False
                self.only_show_remove_messages = True if (
                    self.config['PRUNE']
                    ['ONLY_SHOW_REMOVE_MESSAGES'] == "ON") else False
                self.verbose_logging = True if (
                    self.config['PRUNE']['VERBOSE_LOGGING'] == "ON") else False
                self.video_extensions = list(
                    self.config['PRUNE']
                    ['VIDEO_EXTENSIONS_MONITORED'].split(","))
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
                self.unwanted_genres = list(
                    self.config['PRUNE']['UNWANTED_GENRES'].split(","))

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

    def run(self):
        if not self.enabled_run:
            logging.info(
                "Prune - Library purge disabled.")
            self.writeLog(False, "Prune - Library purge disabled.\n")
            sys.exit()

        # Connect to Sonarr
        if self.sonarr_enabled:
            self.sonarrNode = SonarrAPI(
                self.sonarr_url, self.sonarr_token)
        else:
            logging.info(
                "Prune - Sonarr disabled in INI, exting.")
            self.writeLog(False, "Sonarr disabled in INI, exting.\n")
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
        if self.sonarr_enabled:
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
                isRemoved, isPlanned = self.evalSerie(serie)
                if isRemoved:
                    numDeleted += 1
                if isPlanned:
                    numNotifified += 1

        txtEnd = (
            f"Prune - There were {numDeleted} movies removed "
            f"and {numNotifified} movies planned to be removed "
            f"within {self.warn_days_infront} days."
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
                f"Sonarr - Pruned {numDeleted} movies "
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


if __name__ == '__main__':

    sonarrprune = SONARRPRUNE()
    sonarrprune.run()
    sonarrprune = None
