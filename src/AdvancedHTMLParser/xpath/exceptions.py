'''
    Copyright (c) 2019 Timothy Savannah under terms of LGPLv3. All Rights Reserved.

    See LICENSE (https://gnu.org/licenses/lgpl-3.0.txt) for more information.

    See: https://github.com/kata198/AdvancedHTMLParser for full information


    xpath.exceptions.py - Exceptions related to the XPath engine

'''
# vim: set ts=4 sw=4 st=4 expandtab :


# TODO: Rename this file as xpath_exceptions.py

__all__ = ('XPathBaseError', 'XPathParseError', 'XPathRuntimeError', 'XPathNotImplementedError', )


class XPathBaseError(Exception):
    '''
        XPathBaseError - The base exception class generated by the XPath engine for XPath related issues
    '''

class XPathParseError(XPathBaseError):
    '''
        XPathParseError - Exception raised when there is a parsing error for a provided XPath string.
    '''
    pass

class XPathRuntimeError(XPathBaseError):
    '''
        XPathRuntimeError - Exception raised when some error occurs during runtime (like trying to compare "hello" < 5 )
    '''
    pass

class XPathNotImplementedError(XPathBaseError):
    '''
        XPathNotImplementedError - Exception raised when a XPath feature is requested that is not yet implemented

            by AdvancedHTMLParser's XPath engine, and is recognized as so.
    '''
    pass


# vim: set ts=4 sw=4 st=4 expandtab :
