# !/usr/bin/python
#
# Copyright (C) 2017  Daniel Friedrich
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# si viewprojecthistory --fields=revision --hostname tbd --project=c:/.../project.pj
# si mods --recurse --showAttrChanges --showMemberChanges --project=c:/.../project.pj --hostname tbd -r 1.x -r 1.x
# si viewproject --project=c:/.../project.pj --projectRevision=1.2 --hostname tbd --fields=memberarchive

import subprocess
import time
import csv

cfg_project = "c:/.../project.pj"
cfg_project_cfg_path = "#c:/.../"
cfg_hostname = "tbd"
cfg_output = "ptc2gource_history.txt"
cfg_pathprefix = "/"


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def run_cmd(cmd):
    process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = process.communicate()
    return out


def run_ptc_cmd(cmd):
    out = run_cmd(cmd)
    if out.startswith("***"):
        raise Exception(out)
    return out


def get_author(project, member, member_revision):
    out = run_ptc_cmd("si rlog --noHeaderFormat --noTrailerFormat --fields=author --project=" + project + " --hostname=" + cfg_hostname + " --revision=" + member_revision + " " + member).splitlines()[0]
    if out.find("(") != -1:
        out = out.split('(')[1][:-1]
    return out


def get_date(project, member, member_revision):
    out = run_ptc_cmd("si rlog --noHeaderFormat --noTrailerFormat --fields=date --project=" + project + " --hostname=" + cfg_hostname + " --revision=" + member_revision + " " + member).splitlines()[0]
    out = str(time.mktime(time.strptime(out, '%d.%m.%Y %H:%M:%S')))[:-2]
    return out


def log_commit(csvout, build_project, member, revision, type):
    if member.lower().endswith(".h") or member.lower().endswith(".c"):
        out = [get_date(build_project, member, revision), get_author(build_project, member, revision), type, cfg_pathprefix + build_project[build_project.rfind("#")+1:] + "/" + member]
        print out
        csvout.append(out)


def get_build_project(project, project_revision):
    return project.replace(cfg_project[:-10], cfg_project_cfg_path + "#b=" + project_revision + "#").replace("/project.pj", "")

out = run_ptc_cmd("si viewprojecthistory --fields=revision --project=" + cfg_project + " --hostname=" + cfg_hostname)
out = out.splitlines()
project_revisions = []
for r in out:
    if is_number(r):
        project_revisions.append(r)
project_revisions = list(reversed(project_revisions))
# print project_revisions
csvout = []
for index in range((len(project_revisions) - 1)):
    project_diff = run_ptc_cmd("si mods --recurse --showAttrChanges --showMemberChanges --showRevDescription --project=" + cfg_project + " --hostname=" + cfg_hostname + " -r " + project_revisions[index] + " -r " + project_revisions[index+1])
    print "NEXTDIFF r" + project_revisions[index] + " r" + project_revisions[index+1] + project_diff
    project_diff = project_diff.splitlines()
    build_project = ""
    build_project_next = ""
    member = ""
    modifiedSection = False
    i = 0
    while i < len(project_diff):
        line_parts = project_diff[i].strip().split(' ')

        # Added subproject: c:/.../project.pj at checkpoint 1.x
        # Dropped subproject: c:/.../project.pj at checkpoint 1.x
        # Subproject changed: c:/.../project.pj was "c:/.../project.pj <default>" changed to "c:/.../project.pj [1.5]"
        if (project_diff[i].find("Added subproject: ") != -1) or (project_diff[i].find("Dropped subproject: ") != -1) or (project_diff[i].find("Subproject changed: ") != -1):
            # #c:/...#...#b=1.2#...
            build_project = get_build_project(line_parts[2], project_revisions[index])
            build_project_next = get_build_project(line_parts[2], project_revisions[index+1])
            i += 1
            modifiedSection = False
            continue

        # Subproject checkpoint changed: c:/.../project.pj from 1.x to 1.x
        if project_diff[i].find("Subproject checkpoint changed: ") != -1:
            build_project = get_build_project(line_parts[3], project_revisions[index])
            build_project_next = get_build_project(line_parts[3], project_revisions[index+1])
            i += 1
            modifiedSection = False
            continue

        # Added member: Example.c now at revision 1.x
        if project_diff[i].find("Added member: ") != -1:
            member = line_parts[2]
            revision = line_parts[6]
            log_commit(csvout, build_project_next, member, revision, 'A')
            i += 1
            modifiedSection = False
            continue

        # Dropped member: Example.c at revision 1.1
        if project_diff[i].find("Dropped member: ") != -1:
            member = line_parts[2]
            revision = line_parts[5]
            log_commit(csvout, build_project, member, revision, 'D')
            i += 1
            modifiedSection = False
            continue

        # Member revision changed: Example.c from 1.10 to 1.12
        # 1.10 Manfred Mustermann mustma1 (mustma1) 23.06.2016 15:32:28 IN_WORK --
        # 1.10 log=> bla bla bla
        if project_diff[i].find("Member revision changed: ") != -1:
            member = line_parts[3]
            modifiedSection = True
            i += 2  # skip "from" version
            continue
        if modifiedSection is True:
            if project_diff[i].endswith(" --") and ("log=>" not in line_parts[1]):
                revision = line_parts[0]
                log_commit(csvout, build_project, member, revision, 'M')
            i += 1
            continue

        raise Exception(project_diff[i])

csvout = sorted(csvout, key=lambda row: row[0], reverse=False)
with open(cfg_output, 'w') as file:
    writer = csv.writer(file, delimiter='|', lineterminator='\n')
    writer.writerows(csvout)
