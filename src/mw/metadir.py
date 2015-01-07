###
# mw - VCS-like nonsense for MediaWiki websites
# Copyright (C) 2011  Ian Weller <ian@ianweller.org> and others
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
###

import bzrlib.diff
import codecs
import ConfigParser
import json
import os
from StringIO import StringIO
import sys
import hashlib

version = 'merkys/1'

class Metadir(object):

    def __init__(self):
        self.me = os.path.basename(sys.argv[0])
        root = os.getcwd()
        while True:
            if '.mw' in os.listdir(root):
                self.root = root
                break
            head = os.path.split(root)[0]
            if head == root:
                self.root = os.getcwd()
                break
            root = head
        self.location = os.path.join(self.root, '.mw')
        self.config_loc = os.path.join(self.location, 'config')
        self.version_loc = os.path.join(self.location, 'version')
        if os.path.isdir(self.location) and \
           os.path.isfile(self.config_loc) and \
           os.path.isfile(self.version_loc):
            fd = file(self.version_loc, 'r+')
            if fd.read() != version:
                print '%s: mw repo is incompatible' % self.me
                sys.exit(1)
            fd.close()
            self.config = ConfigParser.RawConfigParser()
            self.config.read(self.config_loc)
            self.pagedict_loaded = False
        else:
            self.config = None

    def save_config(self):
        with open(self.config_loc, 'wb') as config_file:
            self.config.write(config_file)

    def create(self, api_url):
        # create the directory
        if os.path.isdir(self.location):
            print '%s: you are already in a mw repo' % self.me
            sys.exit(1)
        else:
            os.mkdir(self.location, 0755)
        # metadir versioning
        fd = file(os.path.join(self.location, 'version'), 'w')
        fd.write(version)  # XXX THIS API VERSION NOT LOCKED IN YET
        fd.close()
        # create config
        self.config = ConfigParser.RawConfigParser()
        self.config.add_section('remote')
        self.config.set('remote', 'api_url', api_url)
        self.config.add_section('merge')
        self.config.set('merge', 'tool', 'kidff3 %s %s -o %s')
        self.save_config()
        # create cache/
        os.mkdir(os.path.join(self.location, 'cache'))
        # create cache/pagedict
        fd = file(os.path.join(self.location, 'cache', 'pagedict'), 'w')
        fd.write(json.dumps({}))
        fd.close()

        # create pages/
        os.mkdir(os.path.join(self.location, 'pages'), 0755)

    def clean_page(self, filename):
        """
        Seems to remove the trailing newline from the page.
        """
        cur_content = codecs.open(filename, 'r', 'utf-8').read()
        if len(cur_content) != 0 and cur_content[-1] == '\n':
            cur_content = cur_content[:-1]
        fd = file(filename, 'w')
        fd.write(cur_content.encode('utf-8'))
        fd.close()

    def get_pagefile_from_pagename(self, pagename):
        return os.path.join(self.location, 'pages',
                            pagename_to_filename(pagename) + '.wiki')

    def get_pagename_from_filename(self, filename):
        name = os.path.split(filename)[1]
        return filename_to_pagename(name)[:-5]

    def get_pagefile_from_filename(self, filename):
        pagename = self.get_pagename_from_filename(filename)
        return self.get_pagefile_from_pagename(pagename)

    def get_filename_from_pagename(self, pagename):
        return pagename_to_filename(pagename) + '.wiki'

    def get_conflictpath_from_filename(self, filename):
        return filename[:-5] + ".mine"

    def get_pagedata(self, pagename):
        fd = file(self.get_pagefile_from_pagename(pagename),'r')
        return json.loads(fd.read())

    def get_content(self, pagename):
        return self.get_pagedata(pagename)['content']

    def get_author(self, pagename):
        return self.get_pagedata(pagename)['author']

    def get_revision(self, pagename):
        return self.get_pagedata(pagename)['revision']

    def set_content(self, pagename, content, author, revision):
        pagefile = self.get_pagefile_from_pagename(pagename)
        fd = file(pagefile, 'w')
        fd.write(json.dumps({
            'content' : content,
            'author'  : author,
            'revision': revision,
            }))
        fd.truncate()
        fd.close()
            
    def working_dir_status(self, files=None):
        status = {}
        check = []
        if files == None or files == []:
            for root, dirs, files in os.walk(self.root):
                if root == self.root:
                    dirs.remove('.mw')
                for name in files:
                    check.append(os.path.join(root, name))
        else:
            for file in files:
                check.append(os.path.join(os.getcwd(), file))
        check.sort()
        for filename in check:
            if filename.endswith('.wiki'):
                status[filename] = self.get_status_filename(filename)
        return status

    def get_status_filename(self, filename):
        if not os.path.exists(self.get_pagefile_from_filename(filename)):
            return '?' # not added
        if os.path.exists(self.get_conflictpath_from_filename(filename)):
            return 'C' # conflict
        if self.get_revision(self.get_pagename_from_filename(filename)) is None:
            return 'A' # just added
        if self.diff_rv_to_working(filename) != '':
            return 'M' # modified
        else:
            return None

    def diff_rv_to_working(self, filename):
        pagename = self.get_pagename_from_filename(filename)
        old_content = self.get_content(pagename)
        oldrev = self.get_revision(pagename)
        oldname = ''
        if oldrev is not None:
            oldname = 'a/%s (revision %i)' % (pagename, oldrev)
        else:
            oldname = 'a/%s (uncommitted)' % (pagename)
        old = [i + '\n' for i in \
                   old_content.encode('utf-8').split('\n')]
        cur_content = codecs.open(filename, 'r', 'utf-8').read()
        cur_content = cur_content.encode('utf-8')
        if (len(cur_content) != 0) and (cur_content[-1] == '\n'):
            cur_content = cur_content[:-1]
        newname = 'b/%s (working copy)' % pagename
        new = [i + '\n' for i in cur_content.split('\n')]
        diff_fd = StringIO()
        bzrlib.diff.internal_diff(oldname, old, newname, new, diff_fd)
        diff = diff_fd.getvalue()
        if diff and diff[-1] == '\n':
            diff = diff[:-1]
        return diff


def pagename_to_filename(name):
    name = name.replace(' ', '_')
    name = name.replace('/', '!')
    return name


def filename_to_pagename(name):
    name = name.replace('!', '/')
    name = name.replace('_', ' ')
    return name
