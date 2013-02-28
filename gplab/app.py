import random
from functools import wraps

from flask import Flask, render_template, request, Response, redirect, url_for, flash, abort, jsonify
from flask.ext.assets import Environment, Bundle
from flaskext.babel import gettext, lazy_gettext
from flaskext.babel import Babel

from werkzeug.datastructures import Headers
from werkzeug.routing import BaseConverter

from redisco import models, connection_setup
from redisco.containers import List

from flaskext.wtf import Form, TextField, validators, TextAreaField
from wtforms import ValidationError

import tablib

from raven.contrib.flask import Sentry

app = Flask(__name__)
app.config.from_object('gplab.settings.Config')


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter

connection_setup(**app.config['REDIS_CONF'])

assets = Environment(app)
babel = Babel(app)
sentry = Sentry(app=app)

js = Bundle('js/plugins.js', 'js/scripts.js',
            filters='jsmin', output='js/all.js')
assets.register('js_all', js)

css = Bundle('css/landing.css', 'css/generic.css',
            filters='yui_css', output='css/all.css')
assets.register('css_all', css)


@babel.localeselector
def get_locale():
    locale = None

    if 'lang' in request.view_args:
        subdomain = request.view_args['lang']

        if subdomain in app.config['SUBDOMAINS']:
            locale = app.config['SUBDOMAINS'][subdomain]

    if locale is None:
        locale = request.accept_languages.best_match(app.config['SUBDOMAINS'].values())

    return locale


class Quote(models.Model):
    email = models.Attribute(required=False)
    name = models.Attribute(required=False)
    author = models.Attribute(required=True)
    text = models.Attribute(required=True)
    created_at = models.DateTimeField(auto_now_add=True)
    valid = models.BooleanField(default=False, indexed=True)


class Contact(models.Model):
    email = models.Attribute(required=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.Attribute(required=False)


class QuoteForm(Form):
    name = TextField(lazy_gettext('Name'), [
        validators.Optional(),
        validators.Length(min=4, max=25),
    ])
    email = TextField(lazy_gettext('Email Address'), [
        validators.Optional(),
        validators.Email(message=lazy_gettext('Invalid email address.')),
        validators.Length(min=6, max=35)
    ])
    author = TextField(lazy_gettext('Author'), [
        validators.Required(),
        validators.Length(min=4, max=25),
    ])
    text = TextAreaField(lazy_gettext('Text'), [
        validators.Required(),
    ])


class ContactForm(Form):
    email = TextField(lazy_gettext('Email Address'), [
        validators.Required(),
        validators.Email(message=lazy_gettext('Invalid email address.')),
        validators.Length(min=6, max=35)
    ])

    def validate_email(form, field):
        contacts = Contact.objects.filter(email=field.data)

        if len(contacts):
            raise ValidationError(lazy_gettext('Sorry, you can\'t register twice with this email address'))


def check_auth(username, password):
    return username == app.config['USERNAME'] and password == app.config['PASSWORD']


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()

        return f(*args, **kwargs)
    return decorated


def get_random_quote(exclude=None):

    if exclude is None:
        exclude = []

    quote_valid_ids = List('quote_valid_ids').members

    for identifier in exclude:
        quote_valid_ids.remove(identifier)

    quote = None

    length = len(quote_valid_ids)

    if length:
        quote_id = random.randint(0, length - 1)
        quote = Quote.objects.get_by_id(quote_valid_ids[quote_id])

    return quote

@app.route('/', methods=['GET'], subdomain=app.config['DEFAULT_SUBDOMAIN'])
def delegate():
    locale = request.accept_languages.best_match(app.config['SUBDOMAINS'].values())

    scheme_url = 'https://' if request.is_secure else 'http://'

    redirect_url = '%s%s.%s%s' % (
        scheme_url,
        dict((value, key) for key, value in app.config['SUBDOMAINS'].iteritems()).get(locale, app.config['BABEL_DEFAULT_LOCALE']),
        app.config['SERVER_NAME'],
        request.path
    )

    return redirect(redirect_url)


@app.route('/', methods=['GET', 'POST'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
def home(lang):

    quote_form = QuoteForm(prefix='quote_form')

    contact_form = ContactForm(prefix='contact_form')

    quote = get_random_quote()

    if request.method == 'POST':

        if 'submit_quote' in request.form:
            quote_form.process(request.form)

            if quote_form.validate():
                quote = Quote()
                quote_form.populate_obj(quote)
                quote.save()

                l = List('quote_ids')
                l.append(quote.id)

                flash(gettext('Your quote has been successfully added and will be reviewed shortly!'), 'success')

                return redirect(url_for('home', lang=lang))

        if 'submit_contact' in request.form:
            contact_form.process(request.form)

            if contact_form.validate():
                contact = Contact()
                contact.ip_address = request.remote_addr
                contact_form.populate_obj(contact)
                contact.save()

                flash(gettext('Your contact has been successfully added! You will be notified by email when Gamesplanet Lab goes live. In the meantime: have fun!'), 'success')

                return redirect(url_for('home', lang=lang))

    return render_template('home.html', **{
        'quote_form': quote_form,
        'contact_form': contact_form,
        'quote': quote,
        'lang': lang
    })


@app.route('/admin/quotes', methods=['GET', 'POST'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
@requires_auth
def quotes(lang):
    quotes = Quote.objects.all().order('-created_at')

    return render_template('quotes.html', quotes=quotes, lang=lang, contacts_count=len(Contact.objects.all()))


@app.route('/faq', methods=['GET'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
def faq(lang):
    return render_template('faq.html')


@app.route('/commitments', methods=['GET'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
def commitments(lang):
    return render_template('commitments.html')


@app.route('/random', methods=['POST'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
def quote_random(lang):
    kwargs = {
    }

    if not 'quote_id' in request.form:
        kwargs['exclude'] = [request.form['quote_id']]

    quote = get_random_quote(**kwargs)

    if not quote:
        abort(401)

    return jsonify(
        id=quote.id,
        author=quote.author,
        text=quote.text
    )


@app.route('/admin/contacts/export', methods=['GET'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
@requires_auth
def contacts_export(lang):
    headers = ('email', 'creation date')

    contacts = Contact.objects.all().order('-created_at')

    data = []

    for contact in contacts:
        data.append((contact.email, contact.date_creation.strftime("%Y-%m-%d %H:%M:%S") \
                     if hasattr(contact, 'date_creation') and not contact.date_creation is None else '',))

    data = tablib.Dataset(*data, headers=headers)

    headers = Headers()
    headers.add('Content-Disposition', 'attachment', filename='contacts.xls')

    return app.response_class(data.xls, mimetype='application/vnd.ms-excel', headers=headers)


@app.route('/admin/quotes/change', methods=['POST'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
@requires_auth
def quote_change_status(lang):

    if not 'quote_id' in request.form:
        abort(401)

    quote = Quote.objects.get_by_id(request.form['quote_id'])
    if not quote:
        abort(401)

    quote.valid = not quote.valid
    quote.save()

    l = List('quote_valid_ids')

    if quote.valid:
        l.append(quote.id)
    elif quote.id in l:
        l.remove(quote.id)

    return jsonify(id=quote.id, valid=quote.valid)


@app.route('/admin/quotes/edit/<quote_id>', methods=['POST'], subdomain='<regex("%s"):lang>' % '|'.join(app.config['SUBDOMAINS'].keys()))
@requires_auth
def quote_edit(quote_id, lang):
    quote = Quote.objects.get_by_id(quote_id)

    if not quote:
        abort(404)

    changed = False
    if 'author' in request.form:
        quote.author = request.form['author']
        changed = True

    if 'text' in request.form:
        quote.text = request.form['text']
        changed = True

    if changed:
        quote.save()

    return jsonify(id=quote.id, author=quote.author, text=quote.text)


if __name__ == '__main__':
    app.run()
