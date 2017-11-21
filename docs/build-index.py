#!/usr/bin/env python3

"""
The [swagger-ui](https://github.com/swagger-api/swagger-ui) package recommends
modifying the distributed `index.html` to customize it. Hand modifying upstream
distributed resources is problematic when upstream modifies a resource:

- You can re-add your modifications. This requires hand maintaining a "diff" (a
  series of instructions to modify the `index.html`) and then having a human
  read those instructions and follow them on every update (a "patch").

- You can make the modifications once and then continually diverge from
  upstream. This is a particularly bad idea for `swagger-ui` since the
  `index.html` defines SVG icons which will definitely change over time,
  leading to subtle UI breakage.

- Or... you can run this script which parses the upstream `index.html`, makes a
  few modifications, and spits out a new one. Updates should be seamless unless
  the `index.html` changes drastically in structure, at which point the
  heuristics will need to be changed.

Running the script
==================

This is a `python3` script.

Install dependencies with `pip install --upgrade -r requirements.txt`.

Then run the script by executing it directly. It should create a new file
called `index.html` in the same directory.
"""

import itertools
import re
from pathlib import Path

from bs4 import BeautifulSoup

def rewrite_link(link_str):
    link_parts = link_str.split('/')
    assert link_parts[0] == '.'

    return '/'.join(itertools.chain(
        ('.', 'node_modules', 'swagger-ui-dist'),
        link_parts[1:],
    ))

current_dir = Path(__file__).parent

with (current_dir / 'node_modules' / 'swagger-ui-dist' / 'index.html').open() as fp:
    soup = BeautifulSoup(fp, 'html5lib')

soup.head.title.string = 'Encircle Public API'

# Find all `link` elements with relative paths
# For example:
#   <link rel="stylesheet" type="text/css" href="./swagger-ui.css" >
# Becomes:
#   <link rel="stylesheet" type="text/css" href="./node_modules/swagger-ui-dist/swagger-ui.css" >
for link in soup.find_all('link', href=re.compile(r'^\./')):
    link['href'] = rewrite_link(link['href'])

# Find all `script` elements with relative paths
# For example:
#   <script src="./swagger-ui-bundle.js"> </script>
# Becomes:
#   <script src="./node_modules/swagger-ui-dist/swagger-ui-bundle.js"> </script>
for script in soup.find_all('script', src=re.compile(r'^\./')):
    script['src'] = rewrite_link(script['src'])

def is_initializer_script(tag):
    """
    Find the inline `script` that initializes the system and replace it wholesale
    We look for a script with:

        - no `src` attribute
        - `window.onload =` in the script string
        - `SwaggerUIBundle(` being constructed

    These heuristics might have to change if `swagger-ui-dist` updates the
    underlying source code.
    """

    if tag.name != 'script':
        return False

    if tag.has_attr('src'):
        return False

    text = tag.get_text()
    if not re.search(r'window\.onload\s*=', text):
        return False

    if not re.search(r'SwaggerUIBundle\s*\(', text):
        return False

    return True

init_scripts = list(soup.find_all(is_initializer_script))
assert len(init_scripts) == 1

init_scripts[0].string = '''
window.onload = function() {
    var parseQuery = function(queryString) {
        var query = {};
        var pairs = (queryString.charAt(0) === '?' ? queryString.substr(1) : queryString).split('&');
        for (var i = 0; i < pairs.length; ++i) {
            var pair = pairs[i].split('=');
            query[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1] || '');
        }
        return query;
    };

    var query = parseQuery(document.location.search);

    var urls = [];

    if (document.location.protocol == 'file:') {
        urls.push({
            url: 'http://localhost:8890/openapi_v3.json',
            name: 'localhost:8890',
        });
    }

    if (query.encircleUrl != null) {
        urls.push({
            url: query.encircleUrl,
            name: query.encircleUrl,
        });
    }

    urls.push({
        url: 'https://api.encircleapp.com/openapi_v3.json',
        name: 'api.encircleapp.com',
    });

    var ui = SwaggerUIBundle({
        urls: urls,
        dom_id: '#swagger-ui',
        defaultModelRendering: 'model',
        validatorUrl: null,
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIStandalonePreset
        ],
        plugins: [
            SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
    });
};
'''

with (current_dir / 'index.html').open('w') as fp:
    fp.write(soup.prettify())
