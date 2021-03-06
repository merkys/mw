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

import codecs
import cookielib
import getpass
import hashlib
import mw.metadir
from optparse import OptionParser, OptionGroup
import os
import simplemediawiki
import subprocess
import sys
import time


class CommandBase(object):

    def __init__(self, name, description, usage=None):
        self.me = os.path.basename(sys.argv[0])
        self.description = description
        if usage is None:
            usage = '%prog ' + name
        else:
            usage = '%%prog %s %s' % (name, usage)
        self.parser = OptionParser(usage=usage, description=description)
        self.name = name
        self.metadir = mw.metadir.Metadir()
        self.shortcuts = []

    def main(self):
        (self.options, self.args) = self.parser.parse_args()
        self.args = self.args[1:]  # don't need the first thing
        self._do_command()

    def _do_command(self):
        pass

    def _login(self):
        user = raw_input('Username: ')
        passwd = getpass.getpass()
        result = self.api.call({'action': 'login',
                                'lgname': user,
                                'lgpassword': passwd})
        if result['login']['result'] == 'Success':
            # cookies are saved to a file
            print 'Login successful! (yay)'
        elif result['login']['result'] == 'NeedToken':
            print 'Login with token'
            result = self.api.call({'action': 'login',
                                    'lgname': user,
                                    'lgpassword': passwd,
                                    'lgtoken': result['login']['token']})
            if result['login']['result'] == 'Success':
                print 'Login successful! (yay)'
            else:
                print 'Login failed: %s' % result['login']['result']
        else:
            print 'Login failed: %s' % result['login']['result']

    def _die_if_no_init(self):
        if self.metadir.config is None:
            print '%s: not a mw repo' % self.me
            sys.exit(1)
        self.api_setup = False

    def _api_setup(self):
        if not self.api_setup: # do not call _api_setup twice
            cookie_filename = os.path.join(self.metadir.location, 'cookies')
            self.api_url = self.metadir.config.get('remote', 'api_url')
            self.api = simplemediawiki.MediaWiki(self.api_url,
                                             cookie_file=cookie_filename)
            self.api_setup = True


class InitCommand(CommandBase):

    def __init__(self):
        usage = 'API_URL'
        CommandBase.__init__(self, 'init', 'start a mw repo', usage)

    def _do_command(self):
        if len(self.args) < 1:
            self.parser.error('must have URL to remote api.php')
        elif len(self.args) > 1:
            self.parser.error('too many arguments')
        self.metadir.create(self.args[0])


class LoginCommand(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'login', 'authenticate with wiki')

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        self._login()


class LogoutCommand(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'logout', 'forget authentication')

    def _do_command(self):
        self._die_if_no_init()
        try:
            os.unlink(os.path.join(self.metadir.location, 'cookies'))
        except OSError:
            pass


class PullCategoryMembersCommand(CommandBase):

    def __init__(self):
        usage = '[options] PAGENAME ...'
        CommandBase.__init__(self, 'pullcat', 'add remote pages to repo '
                             'belonging to the given category', usage)
        self.query_continue = ''

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        pages = []
        pages += self.args
        for these_pages in [pages[i:i + 25] for i in range(0, len(pages), 25)]:
            data = {
                'action': 'query',
                'gcmtitle': '|'.join(these_pages),
                'generator': 'categorymembers',
                'gcmlimit': 500
            }
        if self.query_continue != '':
           data['gcmcontinue'] = self.query_continue

        api_call = self.api.call(data)
        if 'query-continue' in api_call:
            self.query_continue = api_call['query-continue']['categorymembers']['gcmcontinue']
        else:
            self.query_continue = ''
        if api_call != [] :
 
            response = api_call['query']['pages']
            pull_command = PullCommand()
            pull_command.args = []

            for pageid in response.keys():
                 pagename = response[pageid]['title']
                 pull_command.args += [pagename.encode('utf-8')]

            pull_command._do_command()

            if self.query_continue != '':
                 print 'query continue detected - continuing the query'
                 self._do_command()


class PullCommand(CommandBase):
    
    def __init__(self):
        usage = '[options] PAGENAME ...'
        CommandBase.__init__(self, 'pull', 'add remote pages to repo', usage)

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        pages = []
        pages += self.args

        # Pull should work with pagename, filename, or working directory
        converted_pages = []
        if pages == []:
            pages = self.metadir.working_dir_status().keys()
        for filename in pages:
            if '.wiki' in filename:
                converted_pages.append(
                    self.metadir.get_pagename_from_filename(filename))
            else:
                converted_pages.append(filename)
        pages = converted_pages

        # process the files in groups of 25 to be kind to service
        for these_pages in [pages[i:i + 25] for i in 
                range(0, len(pages), 25)]: 
            data = {
                    'action': 'query',
                    'titles': '|'.join(these_pages),
                    'prop': 'info|revisions',
                    'rvprop': 'ids|flags|timestamp|user|comment|content',
            }
            response = self.api.call(data)['query']['pages']
            # for every pageid, returns dict.keys() = {'lastrevid', 'pageid', 'title', 'counter', 'length', 'touched': u'2011-02-02T19:32:04Z', 'ns', 'revisions' {...}}
            for pageid in response.keys():
                pagename = response[pageid]['title']
                
                if 'revisions' not in response[pageid]:
                    print 'skipping:       "%s" -- cannot find page, perhaps deleted' % (pagename)
                    continue
                
                # ['revisions'][0] is the latest revid
                if 'comment' in response[pageid]['revisions'][0]:
                    last_wiki_rev_comment = response[pageid]['revisions'][0]['comment']
                else:
                    last_wiki_rev_comment = ''
                last_wiki_rev_user = response[pageid]['revisions'][0]['user']
                
                # check if working file is modified or if wiki page doesn't exists
                status = self.metadir.working_dir_status()
                filename = self.metadir.get_filename_from_pagename(pagename)
                full_filename = os.path.join(self.metadir.root, filename)
                if full_filename in status and status[full_filename] in ['M']:
                    print 'skipping:       "%s" -- uncommitted modifications ' % (pagename)
                    continue
                if full_filename in status and status[full_filename] in ['A','?']:
                    print 'skipping:       "%s" -- uncommitted file exists ' % (pagename)
                    continue
                if 'missing' in response[pageid].keys():
                    print 'error:          "%s": -- page does not exist, file not created' % \
                            (self.me, pagename)
                    continue

                wiki_revids = sorted([x['revid'] for x in response[pageid]['revisions']])
                last_wiki_revid = wiki_revids[-1]
                print 'pulling:        "%s" : "%s" by "%s"' % (
                    pagename, last_wiki_rev_comment, last_wiki_rev_user)
                self.metadir.set_content(pagename,
                                         response[pageid]['revisions'][0]['*'],
                                         last_wiki_rev_user,
                                         last_wiki_revid,
                                         os.path.relpath(full_filename,
                                                         self.metadir.root))
                with file(full_filename, 'w') as fd:
                    data = response[pageid]['revisions'][0]['*']
                    data = data.encode('utf-8')
                    fd.write(data)


class RevertCommand(CommandBase):

    def __init__(self):
        usage = 'FILES'
        CommandBase.__init__(self, 'revert', 'revert pages', usage)

    def _do_command(self):
        self._die_if_no_init()
        if self.args:
            status = self.metadir.working_dir_status(self.args)
            files_now = []
            for filename,stat in status.iteritems():
                if stat is not None:
                    if stat not in ['!']:
                        os.unlink(filename)
                    files_now.append(filename)
            if files_now:
                pull_command = PullCommand()
                pull_command.args = files_now
                pull_command._do_command()


class StatusCommand(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'status', 'check repo status')
        self.shortcuts.append('st')
        self.parser.add_option('-A', '--all', dest='show_all', action='store_true',
                                default = False,
                                help="show all files' status")

    def _do_command(self):
        self._die_if_no_init()
        status = self.metadir.working_dir_status()
        for filename in sorted(status.keys()):
            stat = status[filename]
            if stat is not None:
                print '%s %s' % (stat, os.path.relpath(filename))


class AddCommand(CommandBase):

    def __init__(self):
        usage = 'FILES'
        CommandBase.__init__(self, 'add', 'add a wiki page', usage)

    def _do_command(self):
        self._die_if_no_init()
        status = self.metadir.working_dir_status()
        for filename,stat in status.iteritems():
            if stat == '?':
                pagename = self.metadir.get_pagename_from_filename(filename)
                if os.path.exists(self.metadir.get_pagefile_from_pagename(pagename)):
                    print 'warning: can not add %s, page with the same ' \
                          'name exists -- skipping' % filename
                    continue
                self.metadir.set_content(pagename, '', '', None,
                                         os.path.relpath(filename,self.metadir.root))


class CleanCommand(CommandBase):
 
    def __init__(self):
        CommandBase.__init__(self, 'clean', 'remove metadata of deleted pages')

    def _do_command(self):
        self._die_if_no_init()
        status = self.metadir.working_dir_status()
        for filename,stat in status.iteritems():
            if stat == '!':
                pagename = self.metadir.get_pagename_from_filename(filename)
                pagefile = self.metadir.get_pagefile_from_pagename(pagename)
                os.unlink(pagefile)


class TouchCommand(CommandBase):

    def __init__(self):
        usage = 'PAGENAMES'
        CommandBase.__init__(self, 'touch',
                             'create files for given page names and add them', usage)

    def _do_command(self):
        self._die_if_no_init()
        for pagename in self.args:
            filename = mw.metadir.pagename_to_filename(pagename) + '.wiki'
            if not os.path.exists(filename):
                with file(filename, 'w') as fd:
                    fd.write("")
            add_command = AddCommand()
            add_command.args = [filename]
            add_command._do_command()


class DiffCommand(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'diff', 'diff wiki to working directory')

    def _do_command(self):
        self._die_if_no_init()
        status = self.metadir.working_dir_status()
        for filename,stat in status.iteritems():
            if stat in ['M']:
                print self.metadir.diff_rv_to_working(filename)


class CommitCommand(CommandBase):

    def __init__(self):
        usage = '[FILES]'
        CommandBase.__init__(self, 'commit', 'commit changes to wiki', usage)
        self.shortcuts.append('ci')
        self.parser.add_option('-m', '--message', dest='edit_summary',
                               help='don\'t prompt for edit summary and '
                               'use this instead')
        self.parser.add_option('-b', '--bot', dest='bot', action='store_true',
                               help='mark actions as a bot (won\'t affect '
                               'anything if you don\'t have the bot right',
                               default=False)
        self.parser.add_option('-w', '--watch', dest='watch',
                               action='store_true',
                               help='watch modified pages', default=False)

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        files_to_commit = 0 # how many files to process
        status = self.metadir.working_dir_status(files=self.args)
        for filename,stat in status.iteritems():
            if stat in ['A','M']:
                print '%s %s' % (stat, filename)
                files_to_commit += 1
        if not files_to_commit:
            print 'nothing to commit'
            sys.exit()
        if self.options.edit_summary == None:
            print 'Edit summary:',
            edit_summary = raw_input()
        else:
            edit_summary = self.options.edit_summary
        for filename,stat in status.iteritems():
            if stat in ['A','M']:
                start_time = time.time()
                files_to_commit -= 1
                # get edit token
                data = {
                        'action': 'query',
                        'prop': 'info|revisions',
                        'intoken': 'edit',
                        'titles': self.metadir.get_pagename_from_filename(filename),
                }
                response = self.api.call(data)
                pages = response['query']['pages']
                pageid = pages.keys()[0]
                if stat in ['M']:
                    revid = pages[pageid]['revisions'][0]['revid']
                    awaitedrevid = \
                        self.metadir.get_revision(self.metadir.get_pagename_from_filename(filename))
                    if revid != awaitedrevid:
                        print 'warning: edit conflict detected on "%s" (%s -> %s) ' \
                                '-- skipping! (try pull first)' % (filename, awaitedrevid, revid)
                        continue
                edittoken = pages[pageid]['edittoken']
                full_filename = os.path.join(self.metadir.root, filename)
                text = codecs.open(full_filename, 'r', 'utf-8').read()
                text = text.encode('utf-8')
                if (len(text) != 0) and (text[-1] == '\n'):
                    text = text[:-1]
                md5 = hashlib.md5()
                md5.update(text)
                textmd5 = md5.hexdigest()
                data = {
                        'action': 'edit',
                        'title': self.metadir.get_pagename_from_filename(filename),
                        'token': edittoken,
                        'text': text,
                        'md5': textmd5,
                        'summary': edit_summary,
                }
                if self.options.bot:
                    data['bot'] = 'bot'
                if self.options.watch:
                    data['watchlist'] = 'watch'
                response = self.api.call(data)
                if 'error' in response:
                    if 'code' in response['error']:
                        if response['error']['code'] == 'permissiondenied':
                            print 'Permission denied -- try running "mw login"'
                            return
                if response['edit']['result'] == 'Success':
                    if 'nochange' in response['edit']:
                        print 'warning: no changes detected in %s - ' \
                                'skipping and removing ending LF' % filename
                        self.metadir.clean_page(filename)
                        continue
                    if stat in ['M'] and response['edit']['oldrevid'] != revid:
                        print 'warning: edit conflict detected on %s (%s -> %s) ' \
                                '-- skipping!' % (file, 
                                response['edit']['oldrevid'], revid)
                        continue
                    data = {
                            'action': 'query',
                            'revids': response['edit']['newrevid'],
                            'prop': 'info|revisions',
                            'rvprop':
                                    'ids|flags|timestamp|user|comment|content',
                    }
                    response = self.api.call(data)['query']['pages']
                    pageid = response.keys()[0]
                    # need to write latest rev to file too, as text may be changed
                    #such as a sig, e.g., -~ =>  -[[User:Reagle|Reagle]]
                    pagename = self.metadir.get_pagename_from_filename(filename)
                    self.metadir.set_content(pagename,
                                             response[pageid]['revisions'][0]['*'],
                                             response[pageid]['revisions'][0]['user'],
                                             response[pageid]['revisions'][0]['revid'],
                                             os.path.relpath(filename,self.metadir.root))
                    with file(filename, 'w') as fd:
                        data = response[pageid]['revisions'][0]['*']
                        data = data.encode('utf-8')
                        fd.write(data)
                    if files_to_commit :
                        end_time = time.time()
                        print time.strftime("%Y-%m-%d - %H:%M:%S", time.gmtime(time.time())) \
                            + " - Committed - " + self.metadir.get_pagename_from_filename(filename) \
                            + " - Files left: " + str(files_to_commit)
                        time_inc = end_time - start_time
                        delay = 10 - time_inc
                        if delay > 0 :
                            print "adjusting throttle - waiting for %.2fs" % delay
                            time.sleep(delay) 
                else:
                    print 'error: committing %s failed: %s' % \
                            (filename, response['edit']['result'])


class WbcreateclaimCommand(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'wbcreateclaim', 'create claim for wikidata')
        self.parser.add_option('-q', '--entity', dest='entity',
                               help='an entity (target) for new claim')
        self.parser.add_option('-p', '--property', dest='property',
                               help='a property of a claim')
        self.parser.add_option('-v', '--value', dest='value',
                               help='a value for the claim')
        self.parser.add_option('-b', '--bot', dest='bot', action='store_true',
                               help='mark actions as a bot (won\'t affect '
                               'anything if you don\'t have the bot right',
                               default=False)

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        # get edit token
        data = {
                'action': 'query',
                'prop': 'info|revisions',
                'intoken': 'edit',
                'titles': self.options.entity,
               }
        response = self.api.call(data)
        pages = response['query']['pages']
        pageid = pages.keys()[0]
        edittoken = pages[pageid]['edittoken']
        data = {
                'action': 'wbcreateclaim',
                'entity': self.options.entity,
                'property': self.options.property,
                'token': edittoken,
                'snaktype': 'value',
                'value': self.options.value,
        }
        if self.options.bot:
            data['bot'] = 'bot'
        response = self.api.call(data)
        if 'error' in response:
            if 'info' in response['error']:
                print 'error: %s' % response['error']['info']
            else:
                print 'error: %s' % response
        if 'success' in response:
            if 'claim' in response:
                if 'id' in response['claim']:
                    print 'success: %s' % response['claim']['id']


class Wbsetqualifier(CommandBase):

    def __init__(self):
        CommandBase.__init__(self, 'wbsetqualifier', 'set qualifier for claim')
        self.parser.add_option('-c', '--claim', dest='claim',
                               help='a claim (target) for qualifier')
        self.parser.add_option('-p', '--property', dest='property',
                               help='a property of a claim')
        self.parser.add_option('-v', '--value', dest='value',
                               help='a value for the claim')
        self.parser.add_option('-b', '--bot', dest='bot', action='store_true',
                               help='mark actions as a bot (won\'t affect '
                               'anything if you don\'t have the bot right',
                               default=False)

    def _do_command(self):
        self._die_if_no_init()
        self._api_setup()
        # get edit token
        data = {
                'action': 'query',
                'prop': 'info|revisions',
                'intoken': 'edit',
                'titles': self.options.claim,
               }
        response = self.api.call(data)
        pages = response['query']['pages']
        pageid = pages.keys()[0]
        edittoken = pages[pageid]['edittoken']
        data = {
                'action': 'wbsetqualifier',
                'claim': self.options.claim,
                'property': self.options.property,
                'token': edittoken,
                'snaktype': 'value',
                'value': self.options.value,
        }
        if self.options.bot:
            data['bot'] = 'bot'
        response = self.api.call(data)
        if 'error' in response:
            if 'info' in response['error']:
                print 'error: %s' % response['error']['info']
            else:
                print 'error: %s' % response
        if 'success' in response:
            if 'claim' in response:
                if 'id' in response['claim']:
                    print 'success: %s' % response['claim']['id']
