# bugzilla4.py - a really simple Python interface to Bugzilla 4.x using xmlrpclib.
#
# Copyright (C) 2008-2012 Red Hat Inc.
# Author: Michal Novotny <minovotn@redhat.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

import bugzilla.base

class Bugzilla4(bugzilla.base.BugzillaBase):
    '''Concrete implementation of the Bugzilla protocol. This one uses the
    methods provided by standard Bugzilla 4.0.x releases.'''

    version = '0.1'
    user_agent = bugzilla.base.user_agent + ' Bugzilla4/%s' % version
    #createbug_required = ('product','component','summary','version')

    createbug_required = ('product','component','summary','version',
                          'op_sys','platform')

    def __init__(self,**kwargs):
        bugzilla.base.BugzillaBase.__init__(self,**kwargs)
        self.user_agent = self.__class__.user_agent

    def _login(self,user,password):
        '''Backend login method for Bugzilla4'''
        return self._proxy.User.login({'login':user,'password':password})

    def _logout(self):
        '''Backend login method for Bugzilla4'''
        return self._proxy.User.logout()

    #---- Methods and properties with basic bugzilla info

    def _getuserforid(self,userid):
        '''Get the username for the given userid'''
        # STUB FIXME
        return str(userid)

    def _getproducts(self):
        '''This throws away a bunch of data that RH's getProdInfo
        didn't return. Ah, abstraction.'''
        product_ids = self._proxy.Product.get_accessible_products()
        r = self._proxy.Product.get_products(product_ids)
        return r['products']
    def _getcomponents(self,product):
        if type(product) == str:
            product = self._product_name_to_id(product)
        r = self._proxy.Bug.legal_values({'product_id':product,'field':'component'})
        return r['values']

    #---- Methods for reading bugs and bug info

    def _getbugs(self,idlist):
        '''Return a list of dicts of full bug info for each given bug id.
        bug ids that couldn't be found will return None instead of a dict.'''
        idlist = map(lambda i: int(i), idlist)
        r = self._proxy.Bug.get_bugs({'ids':idlist, 'permissive': 1})
        bugdict = dict([(b['id'], b) for b in r['bugs']])
        return [bugdict.get(i) for i in idlist]
    def _getbug(self,id):
        '''Return a dict of full bug info for the given bug id'''
        return self._getbugs([id])[0]

   # TODO: Bugzilla4 should support getbugsimple, needs to be implemented
    _getbugsimple = _getbug
    _getbugssimple = _getbugs

    #---- createbug - call to create a new bug

    def _createbug(self,**data):
        '''Raw xmlrpc call for createBug() Doesn't bother guessing defaults
        or checking argument validity. Use with care.
        Returns bug_id'''
        r = self._proxy.Bug.create(data)
        return r['id']

    #---- Methods for interacting with users

    def _createuser(self, email, name=None, password=None):
        '''Create a new bugzilla user directly.

        :arg email: email address for the new user
        :kwarg name: full name for the user
        :kwarg password: a password to use with the account
        '''
        userid = self._proxy.User.create(email, name, password)
        return userid

    def _addcomment(self,id,comment,private=False,
                   timestamp='',worktime='',bz_gid=''):
        '''Add a comment to the bug with the given ID. Other optional
        arguments are as follows:
            private:   if True, mark this comment as private.
            timestamp: Ignored by BZ32.
            worktime:  amount of time spent on this comment, in hours
            bz_gid:    Ignored by BZ32.
        '''
        return self._proxy.Bug.add_comment({'id':id,
                                            'comment':comment,
                                            'private':private,
                                            'work_time':worktime})

    def _getusers(self, ids=None, names=None, match=None):
        '''Return a list of users that match criteria.

        :kwarg ids: list of user ids to return data on
        :kwarg names: list of user names to return data on
        :kwarg match: list of patterns.  Returns users whose real name or
            login name match the pattern.
        :raises xmlrpclib.Fault: Code 51: if a Bad Login Name was sent to the
                names array.
            Code 304: if the user was not authorized to see user they
                requested.
            Code 505: user is logged out and can't use the match or ids
                parameter.

        Available in Bugzilla-3.4+
        '''
        params = {}
        if ids:
            params['ids'] = ids
        if names:
            params['names'] = names
        if match:
            params['match'] = match
        if not params:
            raise bugzilla.base.NeedParamError('_get() needs one of ids,'
                    ' names, or match kwarg.')

        return self._proxy.User.get(params)

    def _query(self,query):
        '''Query bugzilla and return a list of matching bugs.
        query must be a dict with fields like those in in querydata['fields'].
        You can also pass in keys called 'quicksearch' or 'savedsearch' -
        'quicksearch' will do a quick keyword search like the simple search
        on the Bugzilla home page.
        'savedsearch' should be the name of a previously-saved search to
        execute. You need to be logged in for this to work.
        Returns a dict like this: {'bugs':buglist,
                                   'sql':querystring}
        buglist is a list of dicts describing bugs, and 'sql' contains the SQL
        generated by executing the search.
        You can also pass 'limit:[int]' to limit the number of results.
        For more info, see:
        http://www.bugzilla.org/docs/4.0/en/html/api/Bugzilla/WebService/Bug.html
        '''
        if 'bug_id' in query:
            if type(query['bug_id']) is not list:
                query['id'] = query['bug_id'].split(',')
            else:
                query['id'] = query['bug_id']
            del query['bug_id']

        query['include_fields'] = list()
        if 'column_list' in query:
            query['include_fields'] = query['column_list']
            del query['column_list']

        if 'blockedby' in query['include_fields']:
            query['include_fields'].remove('blockedby')
            query['include_fields'].append('blocks')

        if 'bug_id' in query['include_fields']:
            query['include_fields'].remove('bug_id')
            query['include_fields'].append('id')

        ret = self._proxy.Bug.search(query)

        # Unfortunately we need a hack to preserve backwards compabibility with older BZs
        for bug in ret['bugs']:
            tmpstr = []
            if 'flags' in bug:
                for tmp in bug['flags']:
                    tmpstr.append("%s%s" % (tmp['name'], tmp['status']))

                bug['flags'] = ",".join(tmpstr)
            if 'blocks' in bug:
                if len(bug['blocks']) > 0:
                    bug['blockedby'] = ','.join(map(str, bug['blocks']))
                else:
                    bug['blockedby'] = ''
            if 'id' in bug:
                bug['bug_id'] = bug['id']

        return ret

    def _getbugfields(self):
        '''Get the list of valid fields for Bug objects'''
        r = self._proxy.Bug.fields({'include_fields':['name']})
        tmp = [f['name'] for f in r['fields']]
        tmp.append('blockedby')
        return tmp
        # NOTE: the RHBZ version lists 'comments' and 'groups', and strips
        # the 'cf_' from the beginning of custom fields.
