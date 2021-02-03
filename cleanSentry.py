# this script runs buy cron. crontab -e
# 0 4 * * 0 python /somepath/cleanSentry.py

import argparse
import requests
from datetime import datetime, timedelta


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',
                        nargs='?',
                        required=True,
                        dest='host',
                        help='Domain name of Sentry server')
    parser.add_argument('--retention_period',
                        nargs='?',
                        type=int,
                        default=90,
                        dest='retention_period',
                        help='Retention period in days.')
    parser.add_argument('--organization',
                        nargs='?',
                        required=True,
                        dest='organization',
                        help='Name of organization in Sentry')
    parser.add_argument('--token',
                        nargs='?',
                        required=True,
                        dest='token',
                        help='Access token')
    return parser.parse_args()


def main():
    args = parse_args()
    retention_date = datetime.now() - timedelta(days=args.retention_period)
    url = 'https://{0}/api/0/organizations/{1}/releases/'.format(args.host, args.organization)
    url_next = url
    more_pages_available = True
    releases_to_delete = []
    length_of_datetime = len('2020-02-13T09:19:38Z')  # sometimes time without milliseconds

    print('All old releases before {0} will be deleted from {1}'.format(retention_date, args.host))

    while more_pages_available:
        try:
            response = requests.get(url_next, auth=BearerAuth(args.token))
        except requests.exceptions.RequestException as e:
            print('Error while getting list of releases: {}'.format(e))
            return

        data = response.json()
        link = response.headers['Link']
        # 'Link': '<https://.../releases/?&cursor=100:-1:1>; rel="previous"; results="false"; cursor="100:-1:1",
        # <https://.../releases/?&cursor=100:1:0>; rel="next"; results="true"; cursor="100:1:0"',
        links = link.split(", ")
        more_pages_available = False
        if "rel=\"next\"" in links[1] and "results=\"true\"" in links[1]:
            more_pages_available = True
            x = links[1].index(";")
            url_next = links[1][1:x - 1]

        for release in data:
            date_from_json = release['dateCreated']
            if len(date_from_json) > length_of_datetime:
                release_date = datetime.strptime(release['dateCreated'], '%Y-%m-%dT%H:%M:%S.%fZ')
            else:
                release_date = datetime.strptime(release['dateCreated'], '%Y-%m-%dT%H:%M:%SZ')
            if release_date < retention_date:
                releases_to_delete.append(release['version'])

    if not releases_to_delete:
        print('nothing to delete')
        return

    i = 0
    for release in releases_to_delete:
        try:
            response = requests.delete('{0}{1}/'.format(url, release), auth=BearerAuth(args.token))
        except requests.exceptions.RequestException as e:
            print(e)
        print('Code: {0} for release: {1}'.format(response.status_code, release))
        # status_code == 400 means - This release is referenced by active issues and cannot be removed
        if response.status_code == 204:
            i = i + 1

    print('Number of deleted releases is {}'.format(i))


if __name__ == "__main__":
    main()
