import sys
from urllib import urlencode
import urllib2
import urlparse
import gzip
import mimetypes
from StringIO import StringIO
from mapConf import MapConf
from fake_useragent import UserAgent

conf = MapConf(None)

ua = UserAgent(cache=False)
USER_AGENT = ua.random

class SmartRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_301(
            self, req, fp, code, msg, headers)
        result.status = code
        return result

    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_302(
            self, req, fp, code, msg, headers)
        result.status = code
        return result


class DefaultErrorHandler(urllib2.HTTPDefaultErrorHandler):
    def http_error_default(self, req, fp, code, msg, headers):
        result = urllib2.HTTPError(
            req.get_full_url(), code, msg, headers, fp)
        result.status = code
        return result


def encode_post_data_dict(post_data):
    data = []
    for key in post_data.keys():
        data.append(urlencode(key) + '=' + urlencode(post_data[key]))
    return '&'.join(data)


def encode_post_data(post_data):
    data = []
    for x in post_data:
        data.append(urlencode(x[0]) + '=' + urlencode(x[1]))
    return '&'.join(data)


def openAnything(source, etag=None, lastmodified=None, agent=USER_AGENT, post_data=None, files=None):
    if hasattr(source, 'read'):
        return source

    if source == '-':
        return sys.stdin

    if isinstance(post_data, dict):
        post_data_dict = post_data
        post_data = []
        for key in post_data_dict.keys():
            post_data.append((key, post_data_dict[key]))

    protocol = urlparse.urlparse(source)[0]
    if protocol == 'http' or protocol == 'https':
        
        # open URL with urllib2
        request = urllib2.Request(source)
        request.add_header('User-Agent', agent)
        if lastmodified:
            request.add_header('If-Modified-Since', lastmodified)
        if etag:
            request.add_header('If-None-Match', etag)
        if post_data and files:
            content_type, body = encode_multipart_formdata(post_data, files)
            request.add_header('Content-Type', content_type)
            request.add_data(body)
        elif post_data:
            request.add_data(encode_post_data(post_data))
        request.add_header('Accept-encoding', 'gzip')       
        
        return urllib2.urlopen(request)

    # try to open with native open function (if source is a filename)
    try:
        return open(source)
    except (IOError, OSError):
        pass

    # treat source as string
    return StringIO(str(source))


def fetch(source, etag=None, lastmodified=None, agent=USER_AGENT, post_data=None, files=None):
    '''Fetch data and metadata from a URL, file, stream, or string'''
    result = {}
    f = openAnything(source, etag, lastmodified, agent, post_data, files)
    result['data'] = f.read()
    if hasattr(f, 'headers'):
        # save ETag, if the server sent one
        result['etag'] = f.headers.get('ETag')
        # save Last-Modified header, if the server sent one
        result['lastmodified'] = f.headers.get('Last-Modified')
        if f.headers.get('content-encoding') == 'gzip':
            # data came back gzip-compressed, decompress it
            result['data'] = gzip.GzipFile(fileobj=StringIO(result['data'])).read()
    if hasattr(f, 'url'):
        result['url'] = f.url
        result['status'] = 200
    if hasattr(f, 'status'):
        if f.status == 302:
            result['status'] = 200
        else:
            result['status'] = f.status
    f.close()
    return result


def encode_multipart_formdata(fields, files):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return (content_type, body) ready for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(value)
    for (key, filename) in files:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
        L.append('Content-Type: %s' % get_content_type(filename))
        L.append('')
        L.append(open(filename, 'rb').read())
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    #print '--== encode_multipart_formdata:body ==--'
    return content_type, body


def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
