# -*- coding: utf-8 -*-
from zope import schema
import zope
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.z3cform.templates import ZopeTwoFormTemplateFactory
import plone.app.users.browser.register
from zope.publisher.browser import BrowserView
from z3c.form.browser.radio import RadioFieldWidget
from plone.directives import form
from Products.CMFCore.interfaces import ISiteRoot
from plone.app.layout.navigation.interfaces import INavigationRoot
from z3c.form import field, button, validator
from plone import api
from zope.interface import Invalid, Interface
from edeposit.user import MessageFactory as _
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import adapts
from zope.component import getUtility
from zope.component import queryUtility
from plone.z3cform.fieldsets import extensible
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from edeposit.user.producent import IProducent
from edeposit.user.producentuser import IProducentUser
from edeposit.user.producentfolder import IProducentFolder
from edeposit.user.producentadministrator import IProducentAdministrator, ProducentAdministrator
from edeposit.user.producenteditor import IProducentEditor, ProducentEditor
from z3c.form.interfaces import WidgetActionExecutionError, ActionExecutionError, IObjectFactory, IValidator, IErrorViewSnippet
import os.path
import logging
import string
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
from plone.i18n.normalizer.interfaces import IURLNormalizer, IIDNormalizer
from plone.dexterity.browser.add import DefaultAddForm, DefaultAddView
from plone.supermodel import model
from plone.dexterity.utils import getAdditionalSchemata
from Acquisition import aq_inner, aq_base
from Products.CMFDefault.exceptions import EmailAddressInvalid
from zope.interface import invariant, Invalid

# Logger output for this module
logger = logging.getLogger(__name__)

class IProducentAdministrators(model.Schema):
    administrators = zope.schema.List(
        title = _(u'Producent Administrators'),
        description = u'Přidejte alespoň jednoho administrátora',
        required = True,
        value_type = zope.schema.Object( title=_('Producent Administrator'), schema=IProducentAdministrator ),
        unique = False,
        min_length = 1,
    )

class IAdministrator(model.Schema):
    administrator = zope.schema.Object(
        title = _(u'Producent Administrator'),
        description = u"správce přidává editory, upravuje informace o producentovi.",
        required = True,
        schema=IProducentAdministrator,
    )

class IProducentEditors(model.Schema):
    model.fieldset('editors',
                   label = _(u'Producent Editors'),
                   fields = ['editor1','editor2','editor3']

    )
    editor1 = zope.schema.Object(
        title = _(u'Producent Editor'),
        required = False,
        schema=IProducentEditor,
    )
    editor2 = zope.schema.Object(
        title = _(u'Producent Editor'),
        required = False,
        schema=IProducentEditor,
    )
    editor3 = zope.schema.Object(
        title = _(u'Producent Editor'),
        required = False,
        schema=IProducentEditor,
    )


class ProducentAddForm(DefaultAddForm):
    label = _(u"Registration of a producent")
    description = _(u"Please fill informations about user and producent.")
    default_fieldset_label = u"Producent"

    @property
    def additionalSchemata(self):
        schemata =       [IAdministrator,] +\
                         [s for s in getAdditionalSchemata(portal_type=self.portal_type)] +\
                         [IProducentEditors,]
        return schemata

    def updateWidgets(self):
        super(ProducentAddForm, self).updateWidgets()
        self.widgets['IBasic.title'].label=u"Název producenta"

    def getProducentsFolder(self):
        return self.context

    def extractData(self):
        data, errors = super(ProducentAddForm,self).extractData()

        # remove errors for editors than was not used anymore
        def notEditorError(error):
            name = error.widget.name
            return '.IProducentEditors.' not in name
        
        def existedEditorError(error):
            """
            editor error is necessary just in a case data for editor exists.
            Arguments:
            - `error`: editor error
            """
            name = error.widget.name
            fieldName = '.'.join(string.split(name,'.')[2:])
            return fieldName in data.keys()
            
        newErrors = filter(lambda error: notEditorError(error) or existedEditorError(error), errors)
        
        def getErrorView(widget,error):
            view = zope.component.getMultiAdapter( (error, 
                                                    self.request, 
                                                    widget, 
                                                    widget.field, 
                                                    widget.form, 
                                                    self.context), 
                                                   IErrorViewSnippet)
            view.update()
            widget.error = view
            return view

        def getErrors(adata, awidget):
            password, password_ctl = adata.password, adata.password_ctl
            errors = []
            if password != password_ctl:
                widget_password = awidget.subform.widgets['password']
                widget_password_ctl = awidget.subform.widgets['password_ctl']
                error = zope.interface.Invalid('hesla se musi shodovat')
                errors = (getErrorView(widget_password, Invalid('hesla se musi shodovat')), 
                                  getErrorView(widget_password_ctl, Invalid(u'hesla se musí shodovat')))

            if api.user.get(username=adata.username):
                widget_username = awidget.subform.widgets['username']
                errors += (getErrorView(widget_username, Invalid(u"toto uživatelské jméno je už obsazeno, zvolte jiné")),)
            return errors
            

        names = filter(lambda key: data.get(key,None), ['IAdministrator.administrator',
                                                   'IProducentEditors.editor1',
                                                   'IProducentEditors.editor2',
                                                   'IProducentEditors.editor3',
                                               ])

        def getWidget(name):
            widget = self.widgets.get(name,None) \
                     or filter(lambda widget: widget, map(lambda group: group.widgets.get(name,None), self.groups))[0]
            return widget

        newErrorViews =  map(lambda key: getErrors(data[key], getWidget(key)), names)
        return data, newErrors + tuple(filter (lambda errView: errView, newErrorViews))


    @button.buttonAndHandler(_(u"Register"))
    def handleRegister(self, action):
        print "handle registrer"
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        producentsFolder = self.getProducentsFolder()
        # hack for title and description
        data['title'] = data.get('IBasic.title','')
        data['description'] = data.get('IBasic.description','')

        producent = createContentInContainer(producentsFolder, "edeposit.user.producent", **data)

        administratorsFolder = producent['producent-administrators']
        administrator = data['IAdministrator.administrator']
        administrator.title = getattr(administrator,'fullname',None)
        addContentToContainer(administratorsFolder, administrator, False)

        editorsFolder = producent['producent-editors']
        for editor in filter(lambda item: item, 
                             map(lambda key: data.get(key,None),  ['IProducentEditors.editor1',
                                                              'IProducentEditors.editor2',
                                                              'IProducentEditors.editor3',])):
            print "adding editor"
            editor.title=getattr(editor,'fullname',None)
            addContentToContainer(editorsFolder, editor, False)

        if producent is not None:
            wft = api.portal.get_tool('portal_workflow')
            wft.doActionFor(producent,'submit')
            # mark only as finished if we get the new object
            self._finishedAdd = True
            IStatusMessage(self.request).addStatusMessage(_(u"Item created"), "info")
            url = "%s/%s" % (api.portal.getSite().absolute_url(), 'register-with-producent-successed')
            self.request.response.redirect(url)
    pass

class ProducentAddView(DefaultAddView):
    form = ProducentAddForm

class PostLoginView(BrowserView):
    def update(self):
        portal = api.portal.get()
        dashboard_url = os.path.join(portal.absolute_url(),'producents')
        return self.request.redirect(dashboard_url)

class RegisteredView(BrowserView):
    pass

class ProducentAdministratorFactory(object):
    zope.interface.implements(IObjectFactory)
    adapts(Interface, Interface, Interface, Interface)
    
    def __init__(self, context, request, form, widget):
        self.context = context
        self.request = request
        self.form = form
        self.widget = widget

    def __call__(self, value):
        created=createContent('edeposit.user.producentadministrator',**value)
        return created

class ProducentEditorFactory(object):
    zope.interface.implements(IObjectFactory)
    adapts(Interface, Interface, Interface, Interface)
    
    def __init__(self, context, request, form, widget):
        self.context = context
        self.request = request
        self.form = form
        self.widget = widget

    def __call__(self, value):
        created=createContent('edeposit.user.producenteditor',**value)
        return created

class IProducentWithAdministrators(IProducent):
    administrators = zope.schema.List(
        title = _(u'Producent Administrators'),
        description = _(u'Fill in at least one producent administrator'),
        required = True,
        value_type = zope.schema.Object( title=_('Producent Administrator'), schema=IProducentAdministrator ),
        unique = False
    )

def normalizeTitle(title):
    title = u"Cosi českého a. neobratného"
    util = queryUtility(IIDNormalizer)
    result = util.normalize(title)
    return result


class RegistrationForm(ProducentAddForm):
    portal_type = 'edeposit.user.producent'
    template = ViewPageTemplateFile('form.pt')

    def getProducentsFolder(self):
        portal = api.portal.get()
        return portal['producents']


# class RegistrationForm(form.SchemaForm):
#     schema = IProducentWithAdministrators

#     label = _(u"Registration of a producent")
#     description = _(u"Please fill informations about user and producent.")

#     ignoreContext = True
#     enableCSRFProtection = True

#     template = ViewPageTemplateFile('form.pt')
#     prefix = 'producent'

#     def update(self):
#         self.request.set('disable_border', True)
#         super(RegistrationForm, self).update()

#     @button.buttonAndHandler(_(u"Register"))
#     def handleRegister(self, action):
#         data, errors = self.extractData()
#         if errors:
#             self.status = self.formErrorsMessage
#             return
        
#         producentsFolder = api.portal.getSite()['producents']
#         producent = createContentInContainer(producentsFolder, 
#                                              "edeposit.user.producent", 
#                                              **data)
        
#         for administrator in data['administrators']:
#             addContentToContainer(producent['producent-administrators'], 
#                                   administrator,
#                                   False)
#     pass


# class RegistrationForm01(form.SchemaForm):
#     label = _(u"Registration")
#     description = _(u"Please fill informations about user and producent.")

#     ignoreContext = True
#     enableCSRFProtection = True

#     schema = IEnhancedUserDataSchema
#     template = ViewPageTemplateFile('form.pt')

#     def update(self):
#         self.request.set('disable_border', True)
#         super(RegistrationForm, self).update()

#     @button.buttonAndHandler(u"Register")
#     def handleRegister(self, action):
#         data, errors = self.extractData()
#         if errors:
#             self.status = self.formErrorsMessage
#             return

#         properties = dict([ (key,data[key]) for key in schema.getFieldNames(IEnhancedUserDataSchema) 
#                             if key not in ['password','username','password_ctl']])

#         if api.user.get(username=data['username']):
#             raise ActionExecutionError(Invalid(_('Username is already used. Fill in another username.')))

#         user = api.user.create(username=data['username'],
#                                password=data['password'],
#                                properties = properties,
#                                )
#         producent_properties = dict([ (key,data['producent.'+key]) for key in schema.getFieldNames(IProducent) ])
#         if data.get('producent.new_producent',None):
#             portal_catalog = api.portal.get_tool('portal_catalog')
#             brains = portal_catalog({'object_provides': IProducentFolder.__identifier__})
#             if brains:
#                 plone.api.group.add_user(groupname="Producents", user=user)
#                 producentFolder = brains[0].getObject()
#                 with api.env.adopt_user(user=user):
#                     producent = api.content.create(container=producentFolder,type='edeposit.user.producent', title=data['producent.title'],**producent_properties)
#                     plone.api.user.grant_roles(user=user,obj=producent, roles=['E-Deposit: Assigned Producent',])
#                     plone.api.content.transition(obj=producent, transition="submit")
#                 pass
#             pass
#         else:
#             if data['producent']:
#                 plone.api.group.add_user(groupname="Producents", user=user)
#                 producent = plone.api.content.get(UID=data['producent'])
#                 plone.api.user.grant_roles(user=user,obj=producent,roles=['E-Deposit: Assigned Producent',])
#                 producent.reindexObject()
#             pass
#         self.status="Registered!"
#         self.request.response.redirect(os.path.join(api.portal.get().absolute_url(),"@@register-with-producent-successed"))


# @form.validator(field=IEnhancedUserDataSchema['username'])
# def isUnique(value):
#     print "user is already used validation"
#     if api.user.get(username=value):
#         raise Invalid("Your username is already used. Fill in another username.")
#     return True


# class INewProducent(Interface):
#     new_producent = schema.Bool(
#         title=_(u'label_new_producent', default=u'New producent'),
#         description=_(u'help_new_producent',
#                       default=u"Do you wan to create new producent?"),
#         required=False,
#         )

# class IProducentTitle(Interface):
#     title = schema.ASCIILine(
#         title=_(u'label_producent_title', default=u'Producent title'),
#         description=_(u'help_title_producent',
#                       default=_(u"Fill in title of new producent.")),
#         required=False,
#         )

# class RegistrationFormExtender(extensible.FormExtender):
#     adapts(Interface, IDefaultBrowserLayer, RegistrationForm) # context, request, form

#     def __init__(self, context, request, form):
#         self.context = context
#         self.request = request
#         self.form = form
        
#     def update(self):
#         self.add(field.Fields(INewProducent,prefix="producent"), group="producent")
#         self.move('producent.new_producent', before='producent')
#         self.add(field.Fields(IProducent,prefix="producent"), group="producent")
#         self.add(field.Fields(IProducentTitle,prefix="producent"), group="producent")
#         self.move('producent.title', before='producent.home_page')
#         producentFields = [gg for gg in self.form.groups if 'producent' in gg.__name__][0].fields           
#         if 'form.widgets.producent.new_producent' in self.request.form \
#                 and 'selected' in self.request.form['form.widgets.producent.new_producent']:
#             pass
#         else:
#             for ff in producentFields.values():
#                 field_copy = copy.copy(ff.field)
#                 field_copy.required = False
#                 ff.field = field_copy

