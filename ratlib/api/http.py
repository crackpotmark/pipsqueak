"""Support for calling the HTTP/HTTPS API and handling responses."""
import requests
import requests.exceptions as exc
import requests.status_codes


# Exceptions
"""Generic API Error class."""
class APIError(Exception):
    def __init__(self, code=None, details=None, json=None):
        """
        Creates a new APIError.
        :param code: Error code, if any
        :param details: Details, if any
        :param json: JSON response, if available.
        :return:
        """
        self.code = code
        self.details = details
        self.json = json
    def __repr__(self):
        return "<{0.__class__.__name__({0.code}, {0.details!r})>".format(self)
    __str__ = __repr__


"""Indicates a generic error with the API response."""
class BadResponseError(APIError):
    pass


"""Indicates an error parsing JSON data."""
class BadJSONError(BadResponseError):
    def __init__(self, code='2608', details="API didn\'t return valid JSON."):
        super().__init__(code, details)


class UnsupportedMethodError(APIError):
    def __init__(self, code='9999', details="Invalid request method."):
        super().__init__(code, details)


class HTTPError(APIError):
    pass


# Actual API calling
# For known request methods, we call request.<method> directly since it does some preprocessing for us
# All other requests just use requests.request(method, ...)
request_methods = {attr: getattr(requests, attr) for attr in "GET PUT POST".split(" ")}

def urljoin(*parts):
    """
    Join chunks of a URL together.

    The main thing this does is ensure each chunk is separated by exactly one /.

    :param parts: URL components.
    :return: Unified URL string
    """
    def _gen(parts):
        prev = None
        for part in parts:
            if not part:
                continue
            if not prev:
                prev = part
            elif (prev[-1] == '/') != (part[0] == '/'):  # Exactly one slash was present
                prev = part
            # At this point, either zero or two slashes are present.  Which is it?
            elif part[0] == '/':  # Two slashes.
                prev = part[1:]
            else:  # No slashes.
                yield '/'
                prev = part
            yield prev

    return "".join(part for part in _gen(parts))


def call(method, uri, data=None, statuses=None, **kwargs):
    """
    Wrapper function to contact the web API.

    :param method: Request method
    :param uri: URI.  If this is anything other than a string, it is passed to urljoin() first.
    :param data: Data for JSON request body.
    :param **kwargs: Passed to requests.
    :param statuses: If present, a set of acceptable HTTP response codes (including 200).  If not present, the default
        behavior of requests.raise_for_status() is used.
    """
    if not isinstance(uri, str):
        uri = urljoin(uri)
    data = data or {}

    try:
        if method in request_methods:
            response = request_methods[method](uri, json=data)
        else:
            response = requests.request(method.upper(), uri, json=data)
        if not statuses:
            response.raise_for_status()
        elif response.status_code not in statuses:
            raise HTTPError(code=response.status_code, details=requests.status_codes[response.status][0])
    except exc.HTTPError as ex:
        raise HTTPError(code=ex.response.status_code, details=requests.status_codes[ex.response.status_code][0]) from ex
    except exc.RequestException as ex:
        raise BadResponseError from ex
    try:
        json = response.json()
    except ValueError as ex:
        raise BadJSONError() from ex

    if 'errors' in json:
        err = json['errors'][0]
        raise APIError(err.get('code'), err.get('details'), json=json)
    if 'data' not in json:
        raise BadResponseError(details="Did not receive a data field in a non-error response.", json=json)
    return json
