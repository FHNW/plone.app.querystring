from Acquisition import aq_parent
from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.browser.navtree import getNavigationRoot
from Products.CMFPlone.utils import base_hasattr
from collections import namedtuple
from plone.app.layout.navigation.interfaces import INavigationRoot
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Row = namedtuple('Row', ['index', 'operator', 'values'])


def parseFormquery(context, formquery, sort_on=None, sort_order=None):

    if not formquery:
        return {}
    reg = getUtility(IRegistry)

    # Make sure the things in formquery are dictionaries
    formquery = map(dict, formquery)
    
    # Merge  Values
    mquery = list()
    for row in formquery:
        if len(mquery) < 1:
            rdict = {'i': row.get('i',), 'o': row.get('o'), 'v': []}
            if type(row.get('v')) is str:
                rdict['v'].append(row.get('v'))
            elif type(row.get('v')) is list:
                rdict['v'].extend(row.get('v'))
            mquery.append(rdict)
        else:
            for mrow in mquery:
                if row.get('i') == mrow.get('i'):
                    if row.get('o') == mrow.get('o'):
                        if type(row.get('v')) is str:
                            mrow['v'].append(row.get('v'))
                        elif type(row.get('v')) is list:
                            mrow['v'].extend(row.get('v'))
            else:
                rdict = {'i': row.get('i',), 'o': row.get('o'), 'v': []}
                if type(row.get('v')) is str:
                    rdict['v'].append(row.get('v'))
                elif type(row.get('v')) is list:
                    rdict['v'].extend(row.get('v'))
                mquery.append(rdict)   

    query = {}
    for row in mquery:
        operator = row.get('o', None)
        function_path = reg["%s.operation" % operator]

        # The functions expect this pattern of object, so lets give it to
        # them in a named tuple instead of jamming things onto the request
        row = Row(index=row.get('i', None),
                  operator=function_path,
                  values=row.get('v', None))
        kwargs = {}
        parser = resolve(row.operator)
        kwargs = parser(context, row)

        # Special path handling - since multipath queries are possible
        if 'path' in query and 'path' in kwargs:
            query['path']['query'].extend(kwargs['path']['query'])
        # A Index can have more than one operator
        # For example 'Subject is xxx' and 'Subject is not yyy'
        elif row.index in query:
            if kwargs[row.index].keys()[0] not in query[row.index].keys():
                query[row.index].update(kwargs[row.index])
        else:
            query.update(kwargs)

    if not query:
        # If the query is empty fall back onto the equality query
        query = _equal(context, row)

    # Add sorting (sort_on and sort_order) to the query
    if sort_on:
        query['sort_on'] = sort_on
    if sort_order:
        query['sort_order'] = sort_order
    return query


# Query operators

def _contains(context, row):
    return _equal(context, row)


def _equal(context, row):
    return {row.index: {'query': row.values, }}


def _isNot(context, row):
    return {row.index: {'not': row.values, }}


def _isTrue(context, row):
    return {row.index: {'query': True, }}


def _isFalse(context, row):
    return {row.index: {'query': False, }}


def _between(context, row):
    tmp = {row.index:
           {
               'query': sorted(row.values),
               'range': 'minmax',
           },
           }
    return tmp


def _largerThan(context, row):
    tmp = {row.index:
           {
               'query': row.values,
               'range': 'min',
           },
           }
    return tmp


def _lessThan(context, row):
    tmp = {row.index:
           {
               'query': row.values,
               'range': 'max',
           },
           }
    return tmp


def _currentUser(context, row):
    """Current user lookup"""
    mt = getToolByName(context, 'portal_membership')
    user = mt.getAuthenticatedMember()
    return {row.index: {'query': user.getUserName()}}

def _showInactive(context, row):
    """ Current user roles lookup in order to determine whether user should
        be allowed to view inactive content
    """
    mt = getToolByName(context, 'portal_membership')
    user = mt.getAuthenticatedMember()
    value = False
    user_roles = user.getRoles()
    row_values = row.values
    if row_values:
        for role in user_roles:
            if role in row_values:
                value = True
                break
    return {row.index: value}


def _lessThanRelativeDate(context, row):
    """ "Between now and N days from now." """
    # INFO: Values is the number of days
    try:
        values = int(row.values[0])
    except ValueError:
        values = 0
    now = DateTime()
    start_date = now.earliestTime()
    end_date = now + values
    end_date = end_date.latestTime()
    row = Row(index=row.index,
              operator=row.operator,
              values=(start_date, end_date))
    return _between(context, row)


def _moreThanRelativeDate(context, row):
    """ "Between now and N days ago." """
    # INFO: Values is the number of days
    try:
        values = int(row.values[0])
    except ValueError:
        values = 0
    now = DateTime()
    start_date = now - values
    start_date = start_date.earliestTime()
    end_date = now.latestTime()
    row = Row(index=row.index,
              operator=row.operator,
              values=(start_date, end_date))
    return _between(context, row)


def _betweenDates(context, row):
    try:
        start_date = DateTime(row.values[0])
    except DateTime.DateTimeError:
        start_date = DateTime(0)
    try:
        end_date = DateTime(row.values[1])
    except DateTime.DateTimeError:
        row = Row(index=row.index,
                  operator=row.operator,
                  values=start_date)
        return _largerThan(context, row)
    else:
        row = Row(index=row.index,
                  operator=row.operator,
                  values=(start_date, end_date))

        return _between(context, row)


def _today(context, row):
    now = DateTime()
    start_date = now.earliestTime()
    end_date = now.latestTime()
    row = Row(index=row.index,
              operator=row.operator,
              values=(start_date, end_date))
    return _between(context, row)


def _afterToday(context, row):
    row = Row(index=row.index,
              operator=row.operator,
              values=DateTime())
    return _largerThan(context, row)


def _beforeToday(context, row):
    row = Row(index=row.index,
              operator=row.operator,
              values=DateTime())
    return _lessThan(context, row)


def _path(context, row):
    values = row.values[0]
    depth = None
    if '::' in values:
        values, _depth = values.split('::', 1)
        try:
            depth = int(_depth)
        except ValueError:
            pass
    if not '/' in values:
        # It must be a UID
        values = '/'.join(getPathByUID(context, values))
    # take care of absolute paths without nav_root
    nav_root = getNavigationRoot(context)
    if not values.startswith(nav_root):
        values = nav_root + values

    query = {}
    if depth is not None:
        query['depth'] = depth
        # when a depth value is specified, a trailing slash matters on the
        # query
        values = values.rstrip('/')

    query['query'] = [values]

    return {row.index: query}


def _relativePath(context, row):
    # Walk through the tree
    obj = context
    vals = list()
    navroot = getNavigationRoot(context)
    try:
        obj = context.restrictedTraverse(row.values[0])
        vals.append('/'.join(obj.getPhysicalPath()))
    except Exception:
        vals.append('%s/%s' % (navroot, row.values[0]))
    row = Row(index=row.index,
                  operator=row.operator,
                  values=vals)
    return _path(context, row)


# Helper functions
def getPathByUID(context, uid):
    """Returns the path of an object specified by UID"""
    catalog = getToolByName(context, 'portal_catalog')
    brains = catalog.unrestrictedSearchResults(dict(UID=uid))
    if brains:
        return brains[0].getPath()
    return ''
