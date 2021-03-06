# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
# Copyright 2013 IBM Corp.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from babel import localedata
import copy
import gettext
import logging.handlers
import os

import mock

from openstack.common import gettextutils
from tests import utils


LOG = logging.getLogger(__name__)


class GettextTest(utils.BaseTestCase):

    def test_gettext_does_not_blow_up(self):
        LOG.info(gettextutils._('test'))

    def test_gettextutils_install(self):
        gettextutils.install('blaa')
        self.assertTrue(isinstance(_('A String'), unicode))  # noqa

        gettextutils.install('blaa', lazy=True)
        self.assertTrue(isinstance(_('A Message'),  # noqa
                                   gettextutils.Message))

    def test_gettext_install_looks_up_localedir(self):
        with mock.patch('os.environ.get') as environ_get:
            with mock.patch('gettext.install') as gettext_install:
                environ_get.return_value = '/foo/bar'

                gettextutils.install('blaa')

                environ_get.assert_called_once_with('BLAA_LOCALEDIR')
                gettext_install.assert_called_once_with('blaa',
                                                        localedir='/foo/bar',
                                                        unicode=True)

    def test_get_localized_message(self):
        non_message = 'Non-translatable Message'
        en_message = 'A message in the default locale'
        es_translation = 'A message in Spanish'
        zh_translation = 'A message in Chinese'
        message = gettextutils.Message(en_message, 'test_domain')

        # In the Message class the translation ultimately occurs when the
        # message is turned into a string, and that is what we mock here
        def _mock_translation_and_unicode(self):
            if self.locale == 'es':
                return es_translation
            if self.locale == 'zh':
                return zh_translation
            return self.data

        self.stubs.Set(gettextutils.Message,
                       '__unicode__', _mock_translation_and_unicode)

        self.assertEquals(es_translation,
                          gettextutils.get_localized_message(message, 'es'))
        self.assertEquals(zh_translation,
                          gettextutils.get_localized_message(message, 'zh'))
        self.assertEquals(en_message,
                          gettextutils.get_localized_message(message, 'en'))
        self.assertEquals(en_message,
                          gettextutils.get_localized_message(message, 'XX'))
        self.assertEquals(en_message,
                          gettextutils.get_localized_message(message, None))
        self.assertEquals(non_message,
                          gettextutils.get_localized_message(non_message, 'A'))

    def test_get_available_languages(self):
        # All the available languages for which locale data is available
        def _mock_locale_identifiers():
            return ['zh', 'es', 'nl', 'fr']

        self.stubs.Set(localedata,
                       'list' if hasattr(localedata, 'list')
                       else 'locale_identifiers',
                       _mock_locale_identifiers)

        # Only the languages available for a specific translation domain
        def _mock_gettext_find(domain, localedir=None, languages=[], all=0):
            if domain == 'test_domain':
                return 'translation-file' if any(x in ['zh', 'es']
                                                 for x in languages) else None
            return None
        self.stubs.Set(gettext, 'find', _mock_gettext_find)

        domain_languages = gettextutils.get_available_languages('test_domain')
        # en_US should always be available no matter the domain
        # en_US should also always be the first element since order matters
        # finally only the domain languages should be included after en_US
        self.assertTrue('en_US', domain_languages)
        self.assertEquals(3, len(domain_languages))
        self.assertEquals('en_US', domain_languages[0])
        self.assertTrue('zh' in domain_languages)
        self.assertTrue('es' in domain_languages)

        # Clear languages to test an unknown domain
        gettextutils._AVAILABLE_LANGUAGES = []
        unknown_domain_languages = gettextutils.get_available_languages('huh')
        self.assertEquals(1, len(unknown_domain_languages))
        self.assertTrue('en_US' in unknown_domain_languages)


class MessageTestCase(utils.BaseTestCase):
    """Unit tests for locale Message class."""

    def setUp(self):
        super(MessageTestCase, self).setUp()

        def _message_with_domain(msg):
            return gettextutils.Message(msg, 'oslo')

        self._lazy_gettext = _message_with_domain

    def tearDown(self):
        # need to clean up stubs early since they interfere
        # with super class clean up operations
        self.mox.UnsetStubs()
        super(MessageTestCase, self).tearDown()

    def test_message_equal_to_string(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertEqual(result, msgid)

    def test_message_not_equal(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertNotEqual(result, "Other string %s" % msgid)

    def test_message_equal_with_param(self):
        msgid = "Some string with params: %s"
        params = (0, )

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, message)

        result_str = '%s' % result
        self.assertEqual(result_str, message)

    def test_message_injects_nonetype(self):
        msgid = "Some string with param: %s"
        params = None

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, message)

        result_str = '%s' % result
        self.assertIn('None', result_str)
        self.assertEqual(result_str, message)

    def test_message_iterate(self):
        msgid = "Some string with params: %s"
        params = 'blah'

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        # compare using iterators
        for (c1, c2) in zip(result, message):
            self.assertEqual(c1, c2)

    def test_regex_find_named_parameters(self):
        msgid = ("%(description)s\nCommand: %(cmd)s\n"
                 "Exit code: %(exit_code)s\nStdout: %(stdout)r\n"
                 "Stderr: %(stderr)r %%(something)s")
        params = {'description': 'test1',
                  'cmd': 'test2',
                  'exit_code': 'test3',
                  'stdout': 'test4',
                  'stderr': 'test5',
                  'something': 'trimmed'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_regex_find_named_parameters_no_space(self):
        msgid = ("Request: %(method)s http://%(server)s:"
                 "%(port)s%(url)s with headers %(headers)s")
        params = {'method': 'POST',
                  'server': 'test1',
                  'port': 1234,
                  'url': 'test2',
                  'headers': {'h1': 'val1'}}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_regex_dict_is_parameter(self):
        msgid = ("Test that we can inject a dictionary %s")
        params = {'description': 'test1',
                  'cmd': 'test2',
                  'exit_code': 'test3',
                  'stdout': 'test4',
                  'stderr': 'test5',
                  'something': 'trimmed'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_message_equal_with_dec_param(self):
        """Verify we can inject numbers into Messages."""
        msgid = "Some string with params: %d"
        params = [0, 1, 10, 24124]

        messages = []
        results = []
        for param in params:
            messages.append(msgid % param)
            results.append(self._lazy_gettext(msgid) % param)

        for message, result in zip(messages, results):
            self.assertEqual(type(result), gettextutils.Message)
            self.assertEqual(result, message)

            # simulate writing out as string
            result_str = '%s' % result
            self.assertEqual(result_str, message)

    def test_message_equal_with_extra_params(self):
        msgid = "Some string with params: %(param1)s %(param2)s"
        params = {'param1': 'test',
                  'param2': 'test2',
                  'param3': 'notinstring'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_message_object_param_copied(self):
        """Verify that injected parameters get copied."""
        some_obj = SomeObject()
        some_obj.tag = 'stub_object'
        msgid = "Found object: %(some_obj)s"

        result = self._lazy_gettext(msgid) % {'some_obj': some_obj}

        old_some_obj = copy.copy(some_obj)
        some_obj.tag = 'switched_tag'

        self.assertEqual(result, msgid % {'some_obj': old_some_obj})

    def test_interpolation_with_missing_param(self):
        msgid = ("Some string with params: %(param1)s %(param2)s"
                 " and a missing one %(missing)s")
        params = {'param1': 'test',
                  'param2': 'test2'}

        test_me = lambda: self._lazy_gettext(msgid) % params

        self.assertRaises(KeyError, test_me)

    def test_operator_add(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        additional = " with more added"
        expected = msgid + additional
        result = result + additional

        self.assertEqual(type(result), gettextutils.Message)
        self.assertEqual(result, expected)

    def test_operator_radd(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        additional = " with more added"
        expected = additional + msgid
        result = additional + result

        self.assertEqual(type(result), gettextutils.Message)
        self.assertEqual(result, expected)

    def test_get_index(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        expected = 'm'
        result = result[2]

        self.assertEqual(result, expected)

    def test_get_slice(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        expected = msgid[2:-1]
        result = result[2:-1]

        self.assertEqual(result, expected)

    def test_getitem_string(self):
        """Verify using string indexes on Message does not work."""
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        test_me = lambda: result['blah']

        self.assertRaises(TypeError, test_me)

    def test_contains(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertIn('msgid', result)
        self.assertNotIn('blah', result)

    def test_locale_set_does_translation(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)
        result.domain = 'test_domain'
        result.locale = 'test_locale'
        os.environ['TEST_DOMAIN_LOCALEDIR'] = '/tmp/blah'

        self.mox.StubOutWithMock(gettext, 'translation')
        fake_lang = self.mox.CreateMock(gettext.GNUTranslations)

        gettext.translation('test_domain',
                            languages=['test_locale'],
                            fallback=True,
                            localedir='/tmp/blah').AndReturn(fake_lang)
        fake_lang.ugettext(msgid).AndReturn(msgid)

        self.mox.ReplayAll()
        result = result.data
        os.environ.pop('TEST_DOMAIN_LOCALEDIR')
        self.assertEqual(msgid, result)

    def _get_testmsg_inner_params(self):
        return {'params': {'test1': 'blah1',
                           'test2': 'blah2',
                           'test3': SomeObject()},
                'domain': 'test_domain',
                'locale': 'en_US',
                '_left_extra_msg': 'Extra. ',
                '_right_extra_msg': '. More Extra.'}

    def _get_full_test_message(self):
        msgid = "Some msgid string: %(test1)s %(test2)s %(test3)s"
        message = self._lazy_gettext(msgid)
        attrs = self._get_testmsg_inner_params()
        for (k, v) in attrs.items():
            setattr(message, k, v)

        return copy.deepcopy(message)

    def test_message_copyable(self):
        message = self._get_full_test_message()
        copied_msg = copy.copy(message)

        self.assertIsNot(message, copied_msg)

        for k in self._get_testmsg_inner_params():
            self.assertEqual(getattr(message, k),
                             getattr(copied_msg, k))

        self.assertEqual(message, copied_msg)

        message._msg = 'Some other msgid string'

        self.assertNotEqual(message, copied_msg)

    def test_message_copy_deepcopied(self):
        message = self._get_full_test_message()
        inner_obj = SomeObject()
        message.params['test3'] = inner_obj

        copied_msg = copy.copy(message)

        self.assertIsNot(message, copied_msg)

        inner_obj.tag = 'different'
        self.assertNotEqual(message, copied_msg)

    def test_add_returns_copy(self):
        msgid = "Some msgid string: %(test1)s %(test2)s"
        message = self._lazy_gettext(msgid)
        m1 = '10 ' + message + ' 10'
        m2 = '20 ' + message + ' 20'

        self.assertIsNot(message, m1)
        self.assertIsNot(message, m2)
        self.assertIsNot(m1, m2)
        self.assertEqual(m1, '10 %s 10' % msgid)
        self.assertEqual(m2, '20 %s 20' % msgid)

    def test_mod_returns_copy(self):
        msgid = "Some msgid string: %(test1)s %(test2)s"
        message = self._lazy_gettext(msgid)
        m1 = message % {'test1': 'foo', 'test2': 'bar'}
        m2 = message % {'test1': 'foo2', 'test2': 'bar2'}

        self.assertIsNot(message, m1)
        self.assertIsNot(message, m2)
        self.assertIsNot(m1, m2)
        self.assertEqual(m1, msgid % {'test1': 'foo', 'test2': 'bar'})
        self.assertEqual(m2, msgid % {'test1': 'foo2', 'test2': 'bar2'})

    def test_comparator_operators(self):
        """Verify Message comparison is equivalent to string comparision."""
        m1 = self._get_full_test_message()
        m2 = copy.deepcopy(m1)
        m3 = "1" + m1

        # m1 and m2 are equal
        self.assertEqual(m1 >= m2, str(m1) >= str(m2))
        self.assertEqual(m1 <= m2, str(m1) <= str(m2))
        self.assertEqual(m2 >= m1, str(m2) >= str(m1))
        self.assertEqual(m2 <= m1, str(m2) <= str(m1))

        # m1 is greater than m3
        self.assertEqual(m1 >= m3, str(m1) >= str(m3))
        self.assertEqual(m1 > m3, str(m1) > str(m3))

        # m3 is not greater than m1
        self.assertEqual(m3 >= m1, str(m3) >= str(m1))
        self.assertEqual(m3 > m1, str(m3) > str(m1))

        # m3 is less than m1
        self.assertEqual(m3 <= m1, str(m3) <= str(m1))
        self.assertEqual(m3 < m1, str(m3) < str(m1))

        # m3 is not less than m1
        self.assertEqual(m1 <= m3, str(m1) <= str(m3))
        self.assertEqual(m1 < m3, str(m1) < str(m3))

    def test_mul_operator(self):
        message = self._get_full_test_message()
        message_str = str(message)

        self.assertEqual(message * 10, message_str * 10)
        self.assertEqual(message * 20, message_str * 20)
        self.assertEqual(10 * message, 10 * message_str)
        self.assertEqual(20 * message, 20 * message_str)

    def test_to_unicode(self):
        message = self._get_full_test_message()
        message_str = unicode(message)

        self.assertEqual(message, message_str)
        self.assertTrue(isinstance(message_str, unicode))

    def test_upper(self):
        # test an otherwise uncovered __getattribute__ path
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertEqual(msgid.upper(), result.upper())


class LocaleHandlerTestCase(utils.BaseTestCase):

    def setUp(self):
        super(LocaleHandlerTestCase, self).setUp()

        def _message_with_domain(msg):
            return gettextutils.Message(msg, 'oslo')

        self._lazy_gettext = _message_with_domain
        self.buffer_handler = logging.handlers.BufferingHandler(40)
        self.locale_handler = gettextutils.LocaleHandler(
            'zh_CN', self.buffer_handler)
        self.logger = logging.getLogger('localehander_logger')
        self.logger.propogate = False
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.locale_handler)

    def test_emit_message(self):
        msgid = 'Some logrecord message.'
        message = self._lazy_gettext(msgid)
        self.emit_called = False

        def emit(record):
            self.assertEqual(record.msg.locale, 'zh_CN')
            self.assertEqual(record.msg, msgid)
            self.assertTrue(isinstance(record.msg,
                                       gettextutils.Message))
            self.emit_called = True
        self.stubs.Set(self.buffer_handler, 'emit', emit)

        self.logger.info(message)

        self.assertTrue(self.emit_called)

    def test_emit_nonmessage(self):
        msgid = 'Some logrecord message.'
        self.emit_called = False

        def emit(record):
            self.assertEqual(record.msg, msgid)
            self.assertFalse(isinstance(record.msg,
                                        gettextutils.Message))
            self.emit_called = True
        self.stubs.Set(self.buffer_handler, 'emit', emit)

        self.logger.info(msgid)

        self.assertTrue(self.emit_called)


class SomeObject(object):

    def __init__(self, tag='default'):
        self.tag = tag

    def __str__(self):
        return self.tag

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        for (k, v) in state.items():
            setattr(self, k, v)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.tag == other.tag
        return False
