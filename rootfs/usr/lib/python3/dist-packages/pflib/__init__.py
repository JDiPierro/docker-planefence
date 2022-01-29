# Python3 module of utilities for Plane Fence and Plane Alert
#
# Copyright 2022 Ramon F. Kolb - licensed under the terms and conditions
# of GPLv3. The terms and conditions of this license are included with the Github
# distribution of this package, and are also available here:
# https://github.com/kx1t/planefence/
#
# The package contains parts of, and modifications or derivatives to the following:
# Dump1090.Socket30003 by Ted Sluis: https://github.com/tedsluis/dump1090.socket30003
# These packages may incorporate other software and license terms.
#
# Summary of License Terms
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program.
# If not, see https://www.gnu.org/licenses/.

import os
import tempfile
import shutil
import csv
from datetime import datetime
from os.path import exists

import requests
import discord_webhook as dw

from pflib import embed


DEFAULT_PLANEFILE="/usr/share/planefence/persist/.internal/plane-alert-db.txt"


class InvalidConfigException(Exception):
    pass


def testmsg(msg):
    if os.getenv("TESTING") == "true":
        print(msg)


def init_log(system):
    global log

    def systemlog(msg):
        timestamp = datetime.now().strftime('%c')
        print(f"[{system}][{timestamp}] {msg}")
    log = systemlog


# Global variables
log = None
planedb = {}


def load_config():
    # Load config from the environment as a fallback
    config = {
        "PLANEFILE": os.getenv('PLANEFILE', DEFAULT_PLANEFILE),
        "PA_DISCORD_WEBHOOKS": os.getenv("PA_DISCORD_WEBHOOKS", ""),
        "PF_DISCORD_WEBHOOKS": os.getenv("PF_DISCORD_WEBHOOKS", ""),
        "DISCORD_FEEDER_NAME": os.getenv("DISCORD_FEEDER_NAME", ""),
        "DISCORD_MEDIA": os.getenv("DISCORD_MEDIA", "")
    }

    # Load config
    pfdir = os.getenv("PLANEFENCEDIR", "/usr/share/planefence")
    config_path = f"{pfdir}/planefence.config"
    if exists(config_path):
        with open(config_path) as cfgfile:
            lines = cfgfile.readlines()
            for _, line in enumerate(lines):
                if line.strip().startswith("#"):
                    continue
                split = line.split("=")
                if len(split) == 2:
                    config[split[0].strip()] = split[1].strip()

    if os.getenv("DEBUG", "") == "ON":
        from pprint import pprint; pprint(config)

    # Type conversions
    try:
        config['PA_DISCORD_WEBHOOKS'] = config.get('PA_DISCORD_WEBHOOKS', "").split(',')
        config['PF_DISCORD_WEBHOOKS'] = config.get('PF_DISCORD_WEBHOOKS', "").split(',')
    except:
        raise InvalidConfigException

    load_planefile(config)

    return config


def load_planefile(config):
    global planedb

    planedb = {}
    with open(config['PLANEFILE']) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            #  $ICAO,$Registration,$Operator,$Type,$ICAO Type,#CMPG,$Tag 1,$#Tag 2,$#Tag 3,Category,$#Link
            # Example line:
            #  A51316,N426NA,NASA,Lockheed P-3B Orion,P3,Gov,Sce To Aux,Airborne Science,Wallops Flight Facility,Distinctive,https://www.nasa.gov
            # Skip header and invalid/empty lines
            if row[0].startswith("#") or not row:
                continue

            plane = {
                "icao": row[0],
                "tail_num": row[1],
                "owner": row[2],
                "type": row[3],
                "icao_type": row[4] if len(row) > 4 else "",
                "authority": row[5] if len(row) > 5 else "",
                "tag1": row[6] if len(row) > 6 else "",
                "tag2": row[7] if len(row) > 7 else "",
                "tag3": row[8] if len(row) > 8 else "",
                "category": row[9] if len(row) > 9 else "" ,
                "link": row[10] if len(row) > 10 else ""
            }
            planedb[plane["icao"]] = plane

    log(f"Loaded {len(planedb)} entries into plane-db")


def get_plane_info(icao):
    return planedb.get(icao, {})

def altitude_str(config, alt):
    alt_actual = alt
    alt_type = "MSL"
    alt_unit = "ft"

    if config.get("PF_ALTUNIT", "") == "meter":
        alt_unit = "m"

    elevation = 0
    if config.get("PF_ELEVATION", "").isdigit():
        elevation = int(config["PF_ELEVATION"])

    if elevation > 0:
        alt_actual = alt - elevation
        alt_type = "AGL"

    altstr = '{:,}'.format(alt_actual)
    return f"{altstr}{alt_unit} {alt_type}"

def distance_unit(config):
    cdu = config.get("PF_DISTUNIT", "")

    if cdu == "nauticalmile":
        return "nm"
    if cdu == "kilometer":
        return "km"
    if cdu == "meter":
        return "m"
    return "mi"

def flightaware_link(icao, tail_num):
    icao = icao.strip()
    icao = icao.replace("[", "")
    icao = icao.replace("]", "")
    tail_num = tail_num.strip()
    tail_num = tail_num.replace("[", "")
    tail_num = tail_num.replace("]", "")
    return f"https://flightaware.com/live/modes/{icao}/ident/{tail_num}/redirect"

def is_emergency(squawk):
    return squawk in ('7700', '7600', '7500')

def attach_media(config, subsystem, webhook, embed):
    if config.get('DISCORD_MEDIA', "") == "screenshot":
        snapshot_prefix = "" if subsystem.lower() == "pf" else subsystem.lower()
        snapshot_path = f"/tmp/{snapshot_prefix}snapshot.png"
        testmsg(f"snapshot_path: {snapshot_path}")
        if exists(snapshot_path):
            with open(snapshot_path, "rb") as f:
                webhook.add_file(file=f.read(), filename='snapshot.png')
            embed.set_image(url="attachment://snapshot.png")
        else:
            log("[error] Snapshot file doesn't exist during Discord run")

def send(config, subsystem, embed):
    urls = config[f"{subsystem.upper()}_DISCORD_WEBHOOKS"]

    webhook = dw.DiscordWebhook(url=urls)
    webhook.add_embed(embed)

    testmsg(f"DISCORD_MEDIA: {config['DISCORD_MEDIA']}")
    if config.get('DISCORD_MEDIA', "") != "":
        attach_media(config, subsystem, webhook, embed)

    webhook.execute()
