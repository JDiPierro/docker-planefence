#!/usr/bin/env python3

# Send Discord Alert is a utility for PLANE-ALERT
#
# Usage: ./send-discord-alert.py <inputfile>
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

import sys
import csv

import pflib as pf


# Read the alerts in the input file
def load_alerts(alerts_file):
    alerts = []
    with open(alerts_file) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            # Skip header and invalid lines
            if len(row) < 10 or row[0].startswith("#"):
                continue
            # CSV format is:
            #      ICAO,TailNr,Owner,PlaneDescription,date,time,lat,lon,callsign,adsbx_url,squawk
            alerts.append({
                "icao": row[0].strip(),
                "tail_num": row[1].strip(),
                "owner": row[2].strip(),
                "plane_desc": row[3],
                "date": row[4],
                "time": row[5],
                "lat": row[6],
                "long": row[7],
                "callsign": row[8].strip(),
                "adsbx_url": row[9],
                "squawk": row[10] if len(row) > 10 else "",
            })

    pf.log(f"Loaded {len(alerts)} alerts")
    return alerts


def process_alerts(config, alerts):
    for plane in alerts:
        pf.log(f"Building Discord alert for {plane['icao']}")

        dbinfo = pf.get_plane_info(plane['icao'])

        fa_link = pf.flightaware_link(plane['icao'], plane['tail_num'])

        title = f"Plane Alert - {plane['plane_desc']}"
        color = 0xf2e718
        squawk = plane.get('squawk', "")
        if pf.is_emergency(squawk):
            title = f"Air Emergency! {plane['tail_num']} squawked {squawk}"
            color = 0xff0000

        description = f""
        if plane.get('owner', "") != "":
            description = f"Operated by **{plane.get('owner')}**"
        description += f"\n[Track on ADS-B Exchange]({plane['adsbx_url']})"

        embed = pf.embed.build(title, description, color=color)

        if config.get("DISCORD_FEEDER_NAME", "") != "":
            pf.embed.field(embed, "Feeder", config["DISCORD_FEEDER_NAME"])

        # Attach data fields
        pf.embed.field(embed, "ICAO", plane['icao'])
        pf.embed.field(embed, "Tail Number", f"[{plane['tail_num']}]({fa_link})")

        if plane.get('callsign', "") != "":
            pf.embed.field(embed, "Callsign", plane['callsign'])

        if dbinfo.get('category', "") != "":
            pf.embed.field(embed, "Category", dbinfo['category'])

        if dbinfo.get('tag1', "") != "":
            pf.embed.field(embed, "Tag", dbinfo['tag1'])

        if dbinfo.get('tag2', "") != "":
            pf.embed.field(embed, "Tag", dbinfo['tag2'])

        if dbinfo.get('tag3', "") != "":
            pf.embed.field(embed, "Tag", dbinfo['tag3'])

        if dbinfo.get('link', "") != "":
            pf.embed.field(embed, "Link", f"[Learn More]({dbinfo['link']})")

        # Send the message
        pf.send(config, "PA", embed)


def main():
    pf.init_log("plane-alert/send-discord-alert")

    # Load configuration
    config = pf.load_config()

    if len(sys.argv) != 2:
        print("No input file passed\n\tUsage: ./send-discord-alert.py <inputfile>")
        sys.exit(1)

    input_file = sys.argv[1]

    # Process file and send alerts
    alerts = load_alerts(input_file)
    process_alerts(config, alerts)

    pf.log(f"Done sending alerts to Discord")


if __name__ == "__main__":
    main()
