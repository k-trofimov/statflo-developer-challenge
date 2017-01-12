# coding=utf-8
"""
Exposes a simple HTTP API to search a users Gists via a regular expression.

Github provides the Gist service as a pastebin analog for sharing code and
other develpment artifacts.  See http://gist.github.com for details.  This
module implements a Flask server exposing two endpoints: a simple ping
endpoint to verify the server is up and responding and a search endpoint
providing a search across all public Gists for a given Github account.
"""
import re  # Need this package fo search strings for regular expressions
import requests
from flask import Flask, jsonify, request


# *The* app object
app = Flask(__name__)


@app.route("/ping")
def ping():
    """Provide a static response to a simple GET request."""
    return "pong"


def gists_for_user(username):
    """Provides the list of gist metadata for a given user.

    This abstracts the /users/:username/gist endpoint from the Github API.
    See https://developer.github.com/v3/gists/#list-a-users-gists for
    more information.

    Args:
        username (string): the user to query gists for

    Returns:
        The dict parsed from the json response from the Github API.  See
        the above URL for details of the expected structure.
    """
    gists_url = 'https://api.github.com/users/{username}/gists'.format(
            username=username)

    # BONUS: What failures could happen?
    # SOLUTION:
    # The only failures I can think of are invalid username, non-response
    # from the server and exceeding API rate limit.
    # Invalid username will be handled by the search function.
    # Exceeding API limit will be handled by exception.
    # As for the non-response, there are many types of errors that can cause
    # it, so we will write exception only for ConnectionError as it is the
    # most probable type of non-response prblem.

    try:
        response = requests.get(gists_url).json()

    except ConnectionError:
        print('Could not establish connection \n')

    if type(response) == dict and ('message' in response) and (
        'API rate limit exceeded' in response['message']):

        raise Exception('API rate limit exceeded (But here\'s the good news\
        Authenticated requests get a higher rate limit. Check out the\
        documentation for more details.)')

    # BONUS: Paging? How does this work for users with tons of gists?
    # SOLUTION:
    # By default GitHub paginates the response in chunks of 30 items
    # so if we recieve such response, it is possible that there are more pages
    # with items. We will try to download those next pages one by one until we
    # get an empty page as a response. Then we will stop. Maximum number of
    # attempts is 100 because as per GitHub documentation we can pull maximum
    # of 3000 items
    if len(response) == 30:
        page_indx = 1
        while page_indx < 100:

            page_indx += 1
            next_page_url = gists_url + '?page=' + str(page_indx)

            next_page = requests.get(next_page_url).json()
            if next_page == []:
                page_indx = 100
            response.extend(next_page)

    return response


@app.route("/api/v1/search", methods=['POST'])
def search():
    """Provides matches for a single pattern across a single users gists.

    Pulls down a list of all gists for a given user and then searches
    each gist for a given regular expression.

    Returns:
        A Flask Response object of type application/json.  The result
        object contains the list of matches along with a 'status' key
        indicating any failure conditions.
    """
    post_data = request.get_json()

    # BONUS: Validate the arguments?
    # SOLUTION:
    username = post_data['username']
    if not username.isalnum():
        # Check if username is alphanumeric and nonempty
        raise ValueError('This is not a valid username')

    pattern = post_data['pattern']
    if pattern == '':
        # Check if username is nonempty
        raise ValueError('Pattern string is empty')

    result = {}
    gists = gists_for_user(username)

    # BONUS: Handle invalid users?
    # SOLUTION:
    if type(gists) == dict and ('message' in gists) and (
        gists['message'] == 'Not Found'):

            raise ValueError('User not found')

    result['status'] = 'failure'
    result['username'] = username
    result['pattern'] = pattern
    result['matches'] = []
    for gist in gists:
        # BONUS: What about huge gists?
        # SOLUTION:
        # I will assume that "huge gists" means gists with a lot of files.
        # Since the function only outputs URLs of gists containing pattern
        # it is a waste of time to search for pattern in all of the files
        # in a given gist, if we already found a pattern in one of them.
        # In order to avoid that we will use a boolean indicating if a pattern
        # was found in at least one of the files of a gist. That boolean will
        # trigger a break of the for loop.
        gist_success = False
        for file in gist['files']:

            if gist_success:
                break

            text = requests.get(gist['files'][file]['raw_url']).text
            if re.search(pattern, text):
                gist_url = 'https://gist.github.com/' + username + '/' + gist['id']
                result['matches'].append(gist_url)
                result['status'] = 'success'
                gist_success = True

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
