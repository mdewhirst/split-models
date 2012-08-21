#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Split models out of a monolithic models.py and into separate modules. Thanks
to Patrick Altman's tutorial at ...
   http://paltman.com/2008/01/29/breaking-apart-models-in-django/

Thanks also to all Django developers for making such great software.

This script is in the public domain.

Author = Mike Dewhirst 16 Aug 2012
Python = 2.7
Django = 1.4

17 Aug 2012     Adjusted self.writemeta() to stop inserting db_table and
                generated topline from models.py. Thanks Melvyn Sopacua

21 Aug 2012     Extra '\n' in writemeta

There are no unit tests for this. Run your own app unit tests prior to running
this script and again afterwards. That constitutes the essential testing. This
is a script which is intended to be run once per app then thrown away.

To reverse the process: 1. delete models dir 2. rename models.bak to models.py

In my models.py there are only three types of imports: related models, api
calls on imported models and external imports. ymmv.

There may be other classes in models.py - if so this script ignores them. If
you need to find them look in models/__init__.py

Flow of the script:

Rename models.py to models.bak

scan models.bak and collect all the imports into self.imports including the
new dotted notation for the current directory which in Python 2.7 requires
from __future__ import absolute_import so that the various model files can
do ... from .<model-filename> import <model-class>

write out models.sans w/o imports finally closing models.bak as a true copy
and backup of models.py

scan models.sans for model classes
    write out the class
    analyse it for items to be imported and fill a list with those imports
    insert the imports at the top

This script writes implied imports. An implied import looks like this:

    #from .model.lower import model

... and it appears among the imports with the real ones. It represents the
related models which appear within quotes in the model files.

Constants which appear in the models.py file need to be imported from somewhere
or they get omitted from the split-out files. A convenient spot is inside the
<app>/__init__.py file so they can be ... from <app> import CONST1, CONST2 etc

I had to write a "seemsok" method to detect names embedded within other names

"""

import os

app = 'abc'
home = '/users/miked/py'
project = 'xyz'

aggregate = False   # aggregate imports from the same module

startline = 3 # start inserting import lines into .py files below topline

MODEL = 'models.Model'
OBJ = '.objects'

class Exploder(object):

    def __init__(self, home=home, project=project, app=app,
                                        startline=startline, indent='    '):
        monolith = os.path.join(home, project, app, 'models.py')
        self.app = app
        self.startline = startline
        self.indent = indent

        self.modelspath = monolith.replace('.py', '')
        self.init = os.path.join(self.modelspath, '__init__.py')
        self.bak = monolith.replace('.py', '.bak')
        self.sans = monolith.replace('.py', '.sans')
        if not os.path.isfile(self.bak):
            os.rename(monolith, self.bak)
        if not os.path.isdir(self.modelspath):
            os.mkdir(self.modelspath)
        self.imports = dict()
        self.initlines = list()
        self.init__all = list()
        with open(self.bak, 'r') as self.fbak:
            self.topline = self.maketopline()
            self.fbak.seek(0)
            self.finit = open(self.init, 'w')
            self.finit.write(self.topline)
            with open(self.sans, 'w') as self.fsans:
                self.fillinit()
        self.fsrc = open(self.sans, 'r')
        self.thismodule = None


    def maketopline(self):
        """
        Because this is Django 1.4 and Python 2.7 we need the first line in
        every model file (which uses absolute import) to be from future import
        absolute
        """
        futur_ = 'from __future__ import'
        abs_imp = 'absolute_import'
        future = '%s %s' % (futur_, abs_imp)
        coding = '# -*- coding: utf-8 -*-'
        line1 = self.fbak.readline().strip()
        line2 = self.fbak.readline().strip()
        if 'coding:' in line1:
            coding = line1
        elif 'coding:' in line2:
            coding = line2
        if futur_ in line1 and not abs_imp in line1:
            future = '%s, %s' % (line1, abs_imp)
        return '%s\n%s\n\n' % (future, coding)



    def addimport(self, module, item):
        try:
            vals = self.imports[module]
        except KeyError:
            vals = ''
        if not item == 'self':
            if not item in vals:
                vals += ' %s' % item
        if vals:
            vals = vals.lstrip()
            self.imports[module] = vals


    def aggregatefroms(self, cleaner):
        cleanest = list()
        modules = list()
        ind = self.indent
        #cleaner is in the correct sorted sequence
        for item in cleaner:
            bits = item.split()
            if not bits[1] in modules:
                modules.append(bits[1])
                cleanest.append(item)
            else:
                idx = modules.index(bits[1])
                fromline = cleanest[idx].rstrip()
                chunks = fromline.split('\n')
                if len(chunks[-1]) + len(bits[-1]) > 76:
                    fromline = '%s, \\\n%s%s%s%s' % (fromline, ind, ind, ind, ind)
                    fromline = '%s%s\n' % (fromline,bits[-1])
                else:
                    fromline = '%s, %s\n' % (fromline, bits[-1])
                cleanest[idx] = fromline
        return cleanest


    def checkthisimport(self, item):
        for modulekey in self.imports:
            imports = self.imports[modulekey]
            imps = imports.split()
            for imp in imps:
                if imp == item:
                    return modulekey


    def closefiles(self):
        self.fsrc.close()
        self.finit.close()


    def fillinit(self):
        self.fbak.seek(0)
        while True:
            line = self.fbak.readline()
            if line == '':
                break
            module = ''
            item = ''
            if 'import' in line:
                line2 = ''
                line = line.rstrip()
                while line.endswith('\\'):
                    line = line.replace('\\', '')
                    line2 = self.fbak.readline()
                    line = '%s%s' % (line, line2.strip())
                line += '\n'
                bits = line.strip().split()
                if line.startswith('from'):
                    module = bits[1]
                    item = ' '.join(bits[3:])
                elif line.startswith('import'):
                    item = ' '.join(bits[1:])
                if item:
                    item = item.replace(',', '')
                    self.addimport(module, item)
                    line = 'skip'
            elif 'class' in line and MODEL in line:
                klass = line.split('(')[0].split()[-1]
                # will need to be imported so gets a leading dot
                module = '.%s' % klass.lower()
                self.addimport(module, klass)
                fromline = 'from %s import %s\n' % (module, klass)
                if not fromline in self.initlines:
                    self.initlines.append(fromline)
                if not klass in self.init__all:
                    self.init__all.append(klass)
            elif OBJ in line:
                item = line.split(OBJ)[0].split('=')[-1].split('(')[-1].split('.')[-1]
                item = self.seemsok(item, line)
                if item:
                    item = item.strip()
                    module = self.checkthisimport(item)
                    if not module is None:
                        self.addimport(module, item)
            if not line == 'skip' and not line is None:
                self.fsans.write(line)


    def opennewclass(self):
        if not self.thismodule is None:
            return open('%s.py' % os.path.join(self.modelspath, self.thismodule), 'w')


    def removethismodule(self, clean):
        # we don't want to import from the module we are in
        cleaner = list()
        for line in clean:
            bits = line.split()
            module = bits[-1].strip()
            if not module == module.upper():  # if not a conventional const
                if module.lower() == self.thismodule:
                    continue
            cleaner.append(line)
        return cleaner


    def seemsok(self, item, line):
        low = '><"_abcdefghijklmnopqrstuvwxyz'
        high = low.upper()
        bits = line.split(item)
        if bits[0]:
            prior = bits[0][-1]
            if prior in low or prior in high:
                return ''
            if bits[1]:
                post = bits[1][0]
                if post in low or post in high:
                    return ''
            return item


    def writemeta(self, classpy, module, meta=False):
        xtra = ''
        if meta:
            xtra = '\n'
            classpy.write('%sclass Meta:\n' % self.indent)
        classpy.write("%s%sapp_label = '%s'%s\n" % (self.indent, self.indent,
                                                  self.app, xtra))


    def writemodelfile(self, classpy=None):
        """
        called last thing before a new classpy is opened
        first close classpy coz it is in w mode then open it in r mode
        to pick up the items to import then close it and reopen in w mode
        to insert the froms then close it coz we are done.

        At this point we have all the imports in self.imports (dict) and
        all the lines for the __init__.py file in self.initlines (list) and
        all the classnames in self.init__all (list)

        scan classpy for:
            related models
            items matching the values in self.imports
        and
            insert imports at 'startline' in classpy after topline

        """
        if not classpy is None:
            classpy.close()
            pyfile = '%s.py' % os.path.join(self.modelspath, self.thismodule)
            classpy = open(pyfile, 'r')
            lines = classpy.readlines()
            lines.insert(2, '\n')
            classpy.close()
            froms = list()
            for line in lines:
                prefix = ''
                if 'ForeignKey' in line or 'OneToOneField' in line \
                                        or 'ManyToManyField' in line:
                    idx = lines.index(line)
                    third = ''
                    paren = False
                    comma = False
                    first, second = line.split('(', 1)
                    if not 'self' in second:    # do nothing if it is
                        if ',' in second:       # some options exist
                            second, third = second.split(',', 1)
                            third = ', %s' % third
                        if ')' in second:       # that's all in the line
                            paren = True        # so it can be put back
                            second = second.replace(')', '').strip()
                        if "'" in second:
                            second = second.replace("'", '').strip()
                        if '"' in second:
                            second = second.replace('"', '').strip()
                        relatedmodel = second   # totally naked
                        assert len(second.split()) == 1
                        module = self.checkthisimport(relatedmodel)
                        if not module is None:
                            if module.startswith('.'):
                                prefix = '#'
                                line = "%s('%s'%s" % (first, second, third)
                            else:
                                line = "%s(%s%s" % (first, second, third)
                            if paren:
                                line = '%s)\n' % line.rstrip()
                            if not line.endswith('\n'):
                                line = '%s\n' % line
                            if idx:
                                lines[idx] = line
                            if module:
                                impline = '%sfrom %s import %s\n' % (prefix, module,
                                                                     relatedmodel)
                            else:
                                impline = 'import %s\n' % model
                            if not impline in froms:
                                #print(impline)
                                froms.insert(0, impline)
                # now find all the other imported items
                chunk = line.replace('=', ' ')
                chunk = chunk.replace('[', ' ')
                chunk = chunk.replace('(', ' ')
                chunk = chunk.replace(')', ' ')
                chunk = chunk.replace('.', ' ')
                chunk = chunk.replace(']', ' ')
                chunk = chunk.replace(',', ' ')
                bits = chunk.split()
                for bit in bits:
                    if self.seemsok(bit, line):
                        module = self.checkthisimport(bit)
                        if not module is None:
                            if module == '':
                                impline = 'import %s\n' % bit
                            else:
                                impline = 'from %s import %s\n' % (module, bit)
                            if not impline in froms:
                                froms.insert(0, impline)

            clean = list()
            for item in froms:
                if not '__future__' in item:
                    if not item in clean:
                        clean.insert(0, item)
            cleaner = self.removethismodule(clean)
            del(clean)
            cleaner.sort()
            cleaner.reverse()
            if aggregate:
                cleanest = self.aggregatefroms(cleaner)
            else:
                cleanest = cleaner
            for item in cleanest:
                lines.insert(self.startline, item)
            classpy = open(pyfile, 'w')
            classpy.writelines(lines)
            classpy.close()

#########################################################################

if __name__ == '__main__':

    exp = Exploder(home, project, app, startline)

    meta = True         # otherwise write out a class Meta: line
    classpy = None      # the opened class py file in 'w' mode
    classname = None    # case sensitive derived from the class declaration
    scrap = True        # scraps (non-model classes) go into __init__.py
    init = True         # switch to start off with the __init__.py cycle

    exp.fsrc.seek(0)
    for line in exp.fsrc.readlines():
        if "def __unicode__(self):" in line and not meta:
            exp.writemeta(classpy, classname, True)
        if line[0:5] == 'class' and MODEL in line:
            # still on the old class at this point
            # patch in the froms at the top and close classpy
            exp.writemodelfile(classpy)
            # this is a new class so stop adding stuff to __init__.py
            scrap = False
            # start work on the new class just detected
            classname = line.split('(')[0].split()[1]
            exp.thismodule = classname.lower()
            classpy = exp.opennewclass()
            classpy.write(exp.topline)
            meta = False
        if scrap:
            if not 'import' in line:
                if init:
                    init = False
                    exp.initlines.append('\n\n')
                exp.initlines.append(line)
        else:
            # must be a line in a classpy file so classname must be set already
            if 'class Meta:' in line and not meta:
                meta = True
                classpy.write(line)
                line = ''
                exp.writemeta(classpy, classname)
            if line:
                classpy.write(line)
    # just to get the last one done
    exp.writemodelfile(classpy)
    exp.finit.writelines(exp.initlines)
    exp.finit.write('\n__all__ = %s\n' % exp.init__all)
    exp.closefiles()
