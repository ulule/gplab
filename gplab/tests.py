# -*- coding: utf-8 -*-
import base64

try:
    import simplejson as json
except ImportError:
    import json

import gplab.app as gplab
from gplab.app import Quote, Contact, get_random_quote

from redisco import connection_setup, get_client
from redisco.containers import List

import unittest


class TestCase(unittest.TestCase):

    def setUp(self):
        """Before each test, set up a blank database"""
        gplab.app.config['TESTING'] = True
        gplab.app.config['CSRF_ENABLED'] = False

        connection_setup(host='localhost', port=6379, db=4)

        client = get_client()
        client.flushdb()

        self.app = gplab.app.test_client()

    def test_home(self):
        response = self.app.get('/', base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        self.assertEqual(response.status_code, 200)

    def test_home_quote_complete(self):
        response = self.app.post('/', data={
            'quote_form-name': 'Test',
            'quote_form-email': 'florent.messa@gmail.com',
            'quote_form-author': 'Einstein',
            'quote_form-text': 'Test',
            'submit_quote': 1
        }, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(Quote.objects.all()), 1)

        quote = Quote.objects.get_by_id(1)
        self.assertEqual(quote.name, 'Test')
        self.assertEqual(quote.email, 'florent.messa@gmail.com')
        self.assertEqual(quote.author, 'Einstein')
        self.assertEqual(quote.text, 'Test')
        self.assertEqual(quote.valid, False)

    def test_quote_valid(self):
        self.app.post('/', data={
            'quote_form-name': 'Test',
            'quote_form-email': 'florent.messa@gmail.com',
            'quote_form-author': 'Einstein',
            'quote_form-text': 'Test',
            'submit_quote': 1
        }, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        res = self.open_with_auth('/admin/quotes/change', 'POST',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'], data={
                                      'quote_id': 1
                                  })

        self.assertEqual(res.status_code, 200)

        quote = get_random_quote()

        self.assertTrue(quote is not None)
        self.assertTrue(quote.valid)

        l = List('quote_valid_ids')

        self.assertEqual(len(l.members), 1)
        self.assertTrue(quote.id in l.members)

        res = self.open_with_auth('/admin/quotes/change', 'POST',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'], data={
                                      'quote_id': 1
                                  })

        self.assertEqual(res.status_code, 200)

        quote = get_random_quote()

        self.assertTrue(quote is None)

        quote = Quote.objects.get_by_id(1)

        self.assertFalse(quote.valid)

        l = List('quote_valid_ids')

        self.assertEqual(len(l.members), 0)
        self.assertFalse(quote.id in l.members)

    def test_random_quote(self):
        self.app.post('/', data={
            'quote_form-name': 'Test',
            'quote_form-email': 'florent.messa@gmail.com',
            'quote_form-author': 'Einstein',
            'quote_form-text': 'Test',
            'submit_quote': 1
        }, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        res = self.app.post('/random', data={'quote_id': 1}, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        self.assertEqual(res.status_code, 401)

        res = self.open_with_auth('/admin/quotes/change', 'POST',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'], data={
                                      'quote_id': 1
                                  })

        self.assertEqual(res.status_code, 200)

        res = self.app.post('/random', data={'quote_id': 1}, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        self.assertEqual(res.status_code, 200)

        self.assertEqual(json.loads(res.data), {
            'id': '1',
            'text': 'Test',
            'author': 'Einstein'
        })

    def test_quote_edit(self):
        self.app.post('/', data={
            'quote_form-name': 'Test',
            'quote_form-email': 'florent.messa@gmail.com',
            'quote_form-author': 'Einstein',
            'quote_form-text': 'Test',
            'submit_quote': 1
        }, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        res = self.open_with_auth('/admin/quotes/edit/10', 'POST',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'], data={
                                      'author': 'Test',
                                      'text': 'Test'
                                  })

        self.assertEqual(res.status_code, 404)

        res = self.open_with_auth('/admin/quotes/edit/1', 'POST',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'], data={
                                      'author': 'Test',
                                      'text': 'Test'
                                  })

        self.assertEqual(res.status_code, 200)

        quote = Quote.objects.get_by_id(1)

        self.assertEqual(quote.author, 'Test')
        self.assertEqual(quote.text, 'Test')

    def test_home_contact_complete(self):
        response = self.app.post('/', data={
            'contact_form-email': 'florent.messa@gmail.com',
            'submit_contact': 1
        }, base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])

        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(Contact.objects.all()), 1)

        contact = Contact.objects.get_by_id(1)

        self.assertEqual(contact.email, 'florent.messa@gmail.com')

    def open_with_auth(self, url, method, username, password, data=None):
        return self.app.open(
            url,
            method=method,
            headers={
                'Authorization': 'Basic ' + base64.b64encode(username + \
                                                             ":" + password)
            },
            data=data,
            base_url="http://www.%s" % gplab.app.config['SERVER_NAME']
        )

    def test_quotes(self):
        response = self.app.get('/admin/quotes', base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])
        self.assertEqual(response.status_code, 401)

        res = self.open_with_auth('/admin/quotes',
                                  'GET',
                                  gplab.app.config['USERNAME'],
                                  gplab.app.config['PASSWORD'])

        self.assertEqual(res.status_code, 200)

    def test_contacts_export(self):
        response = self.app.get('/admin/contacts/export', base_url="http://www.%s" % gplab.app.config['SERVER_NAME'])
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
