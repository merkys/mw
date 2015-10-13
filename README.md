mw &mdash; VCS-like nonsense for MediaWiki websites
Copyright (C) 2011 Ian Weller <ian@ianweller.org> and others

Setup
=====

You can install mw with the setup.py.

This package is dependent upon python-simplemediawiki:
  https://github.com/ianweller/python-simplemediawiki

Also, the default merge tool is `kdiff3`, you can change this in your
.mw/config after initialization.

Basic workflow
==============

```
mw init http://example.com/w/api.php
mw login  # if you need/want to
mw pull 'Main Page'
$EDITOR Main_Page.wiki
mw commit
mw status
```

Commands
========

```
usage: mw [subcommand]

        add            add a wiki page
        clean          remove metadata of deleted pages
        commit (ci)    commit changes to wiki
        diff           diff wiki to working directory
        init           start a mw repo
        login          authenticate with wiki
        logout         forget authentication
        pull           add remote pages to repo
        pullcat        add remote pages to repo belonging to the given category
        status (st)    check repo status
        touch          create files for given page names and add them
```

For a brief tutorial, see:
  http://reagle.org/joseph/2011/01/mw-tutorial

Status command
==============

`status` Will show whether a file has been added ('A'), locally modified
  ('M') or missing ('!').

Pull command
============

The `pull` command has the following features:

* Can pull a new page/file, or update one.
* Can be provided a page name or file name.
* If the wiki has updates, it will pull those unless they conflict 
  with local changes. The user must then resolve/merge conflicts.

License
=======

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program.  If not, see <http://www.gnu.org/licenses/>.
