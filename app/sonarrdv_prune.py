# Name: Sonarr Prune
# Coder: Marco Janssen (mastodon @marc0janssen@mastodon.green)
# date: 2023-12-31 19:38:00
# update: 2024-03-09 22:14:00

import argparse
import logging
import configparser
import sys
import shutil
import smtplib
import os
import httpx
import time

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from chump import Application

try:
    from app.sonarr_client import SonarrClient, SonarrClientError
    from app.sonarr_prune_logic import (
        SeasonActionKind,
        decide_season_prune,
        format_warning_time_left,
        resolve_keep_tag_ids,
        season_directory_name,
        series_should_keep,
    )
except ImportError:
    from sonarr_client import SonarrClient, SonarrClientError
    from sonarr_prune_logic import (
        SeasonActionKind,
        decide_season_prune,
        format_warning_time_left,
        resolve_keep_tag_ids,
        season_directory_name,
        series_should_keep,
    )
from socket import gaierror

try:
    from app.version import __version__
except ImportError:
    from version import __version__


class SONARRPRUNE():

    def __init__(self, config_path=None):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO)
        # Keep HTTP client internals quiet unless they are warnings/errors.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

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
            if not os.path.isfile(self.config_filePath):
                raise FileNotFoundError(self.config_filePath)
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

    def trigger_database_update_emby(self, base_url: str, api_key: str, name: str):
        url = f"{base_url}/Emby/Library/Refresh?api_key={api_key}"
        response = httpx.post(url, data={}, headers={}, timeout=60.0)
        if response.status_code == 204:
            logging.info(
                f"Database update triggered successfully for {name}.")
        else:
            logging.error(
                f"Failed to trigger database update for {name}. Status code: "
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
            response = httpx.post(
                self.sonarrdv_url + endpoint,
                json=payload,
                headers=headers,
                timeout=60.0,
            )

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

    def _log_event(self, msg: str):
        self.writeLog(False, f"{msg}\n")
        logging.info(msg)

    def _send_pushover(self, message: str):
        if self.pushover_enabled:
            self.message = self.userPushover.send_message(
                message=message,
                sound=self.pushover_sound,
            )

    def _season_first_complete_at(self, serie, season):
        """First-complete time from marker file mtime, or None if N/A."""
        sdir = season_directory_name(season.seasonNumber)
        base = os.path.join(serie.path, sdir)
        if not os.path.isdir(base):
            return None
        if season.totalEpisodeCount != season.episodeFileCount:
            return None
        fc_path = os.path.join(base, self.firstcomplete)
        if not os.path.isfile(fc_path):
            open(fc_path, "w").close()
            if not self.only_show_remove_messages:
                txt_first = (
                    f"PRUNE: COMPLETE - {serie.title} "
                    f"S{str(season.seasonNumber)} ({serie.year})"
                )
                self._log_event(txt_first)
        mtime = os.stat(fc_path).st_mtime
        return datetime.fromtimestamp(mtime)

    def evalSeason(self, serie, season):
        """Filesystem + notifications; prune rules live in sonarr_prune_logic."""
        season_download_date = self._season_first_complete_at(serie, season)
        if not season_download_date:
            return False, False

        now = datetime.now()
        dec = decide_season_prune(
            now,
            season_download_date,
            remove_after_days=self.remove_after_days,
            warn_days_infront=self.warn_days_infront,
        )

        sdir = season_directory_name(season.seasonNumber)
        season_path = os.path.join(serie.path, sdir)

        if dec.kind == SeasonActionKind.WARN:
            assert dec.time_until_removal is not None
            self.timeLeft = dec.time_until_removal
            txt_time = format_warning_time_left(dec.time_until_removal)
            self._send_pushover(
                f"Prune - {serie.title} "
                f"Season {str(season.seasonNumber).zfill(2)}"
                f" ({serie.year}) "
                f"will be removed from server in "
                f"{txt_time}"
            )
            txt_warn = (
                f"PRUNE: WARNING - {serie.title} "
                f"Season {str(season.seasonNumber).zfill(2)} "
                f"({serie.year}) will be removed in {txt_time}."
            )
            self._log_event(txt_warn)
            return False, True

        if dec.kind == SeasonActionKind.REMOVE:
            if not self.dry_run and self.sonarrdv_enabled:
                try:
                    shutil.rmtree(season_path)
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
            txt_title = (
                f"{serie.title} ({serie.year}) - "
                f"Season {str(season.seasonNumber).zfill(2)}"
            )
            self._send_pushover(
                f"PRUNE: REMOVED - {txt_title} "
                f"(removed: {season_download_date})"
            )
            txt_removed = (
                f"PRUNE: REMOVED - {txt_title} "
                f"(removed: {season_download_date})"
            )
            self._log_event(txt_removed)
            return True, False

        # ACTIVE
        if not self.only_show_remove_messages:
            txt_active = (
                f"PRUNE: ACTIVE - {serie.title} "
                f"Season {str(season.seasonNumber).zfill(2)} "
                f"({serie.year}) - first complete: "
                f"{season_download_date}"
            )
            self._log_event(txt_active)
        return False, False

    def run(self):
        if not self.enabled_run:
            logging.info(
                "Prune - Library purge disabled.")
            self.writeLog(False, "Prune - Library purge disabled.\n")
            sys.exit()

        # Connect to Sonarr DV
        if self.sonarrdv_enabled:
            try:
                self.sonarrNode = SonarrClient(
                    self.sonarrdv_url, self.sonarrdv_token)
            except SonarrClientError as e:
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
        media = self.sonarrNode.all_series()

        logging.info("Sonarr Prune %s", __version__)
        if self.verbose_logging:
            logging.info("Prune - Sonarr Prune %s started.", __version__)
        self.writeLog(
            True,
            f"Prune - Sonarr Prune {__version__} started.\n",
        )

        # Make sure the library is not empty.
        numDeleted = 0
        numNotified = 0

        if media:
            media.sort(key=lambda s: s.sortTitle)
            tags_ids_to_keep = []
            if self.tags_to_keep:
                label_to_id = {
                    tag.label: tag.id for tag in self.sonarrNode.all_tags()
                }
                tags_ids_to_keep = resolve_keep_tag_ids(
                    self.tags_to_keep, label_to_id)

            for serie in media:

                if series_should_keep(serie.tagsIds, tags_ids_to_keep):
                    if not self.only_show_remove_messages:
                        txtKeeping = (
                            f"Prune - KEEPING - {serie.title} ({serie.year})."
                            f" Skipping."
                        )
                        self._log_event(txtKeeping)
                else:
                    subNumDeleted = 0
                    subNumNotified = 0

                    for season in serie.seasons:
                        removed, planned = self.evalSeason(serie, season)
                        if removed:
                            subNumDeleted += 1
                        if planned:
                            subNumNotified += 1

                    numDeleted += subNumDeleted
                    numNotified += subNumNotified

                time.sleep(0.2)

        txtEnd = (
            f"Prune - There were {numDeleted} seasons removed."
        )

        self._send_pushover(txtEnd)

        if self.verbose_logging:
            logging.info(txtEnd)
        self.writeLog(False, f"{txtEnd}\n")

        should_send_mail = self.mail_enabled and (
            not self.only_mail_when_removed
            or numDeleted > 0
            or numNotified > 0
        )
        if should_send_mail:

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
            self.trigger_database_update_emby(
                self.emby_url1, self.emby_token1, "Emby1")

        if self.emby_enabled2:
            self.trigger_database_update_emby(
                self.emby_url2, self.emby_token2, "Emby2")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Prune old Sonarr seasons when they are old enough.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"sonarr_prune {__version__}",
    )
    parser.parse_args()

    sonarrprune = SONARRPRUNE()
    sonarrprune.run()
    sonarrprune = None
