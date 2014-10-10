# -*- coding: utf-8 -*-
from zope.interface import Interface
from zope.interface import implements
from itertools import chain
from plone.app.portlets.portlets import base
from plone.portlets.interfaces import IPortletDataProvider
from plone import api
from zope import schema
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from edeposit.user import MessageFactory as _

from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
from Products.CMFCore.utils import getToolByName
from plone.z3cform.layout import FormWrapper

from z3c.form.interfaces import WidgetActionExecutionError, ActionExecutionError, IObjectFactory
from zope.lifecycleevent import modified
from five import grok
from plone.directives import form
from zope.formlib import form as formlib
from z3c.form import group, field, button

def possibleWorkersFactory(groupName):
    @grok.provider(IContextSourceBinder)
    def possibleWorkers(context):
        acl_users = getToolByName(context, 'acl_users')
        group = acl_users.getGroupById(groupName)
        terms = []
        
        if group is not None:
            for member_id in group.getMemberIds():
                user = acl_users.getUserById(member_id)
                if user is not None:
                    member_name = user.getProperty('fullname') or member_id
                    terms.append(SimpleVocabulary.createTerm(member_id, str(member_id), member_name))
                    
        return SimpleVocabulary(terms)
    return possibleWorkers

possibleDescriptiveCataloguers = possibleWorkersFactory('Descriptive Cataloguers')
possibleDescriptiveReviewers = possibleWorkersFactory('Descriptive Cataloguing Reviewers')
possibleSubjectCataloguers = possibleWorkersFactory('Subject Cataloguers')
possibleSubjectReviewers = possibleWorkersFactory('Subject Cataloguing Reviewers')

class IAssignedDescriptiveCataloguer(form.Schema):
    cataloguer = schema.Choice(
        title=_(u"Cataloguer"),
        source=possibleDescriptiveCataloguers,
        required=False,
    )
class IAssignedDescriptiveReviewer(form.Schema):
    reviewer = schema.Choice(
        title=_(u"Reviewer"),
        source=possibleDescriptiveReviewers,
        required=False,
    )

class IAssignedSubjectCataloguer(form.Schema):
    cataloguer = schema.Choice(
        title=_(u"Cataloguer"),
        source=possibleSubjectCataloguers,
        required=False,
    )

class IAssignedSubjectReviewer(form.Schema):
    reviewer = schema.Choice(
        title=_(u"Reviewer"),
        source=possibleSubjectReviewers,
        required=False,
    )
    
class AssignedWorkerForm(form.SchemaForm):
    schema = IAssignedDescriptiveCataloguer
    ignoreContext = True
    label = u""
    description = u""
    submitAction = 'submitDescriptiveCataloguingPreparing'
    fieldName = 'cataloguer'
    roleName = 'E-Deposit: Descriptive Cataloguer'

    @button.buttonAndHandler(u'Přiřadit')
    def handleOK(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        if data.get(self.fieldName,None):
            local_roles = self.context.get_local_roles()
            remove = filter(lambda pair: self.roleName in pair[1], local_roles)
            users = map(lambda pair: pair[0], remove)
            for userid in users:
                api.user.revoke_roles(username=userid, 
                                      obj=self.context, 
                                      roles=[self.roleName,])
            api.user.grant_roles(username=data[self.fieldName],
                                 obj=self.context, 
                                 roles=[self.roleName,])
            modified(self.context)
            wft = api.portal.get_tool('portal_workflow')
            wft.doActionFor(self.context, self.submitAction)
        self.status = u"Hotovo!"

# @form.default_value(field=IAssignedCataloguer['cataloguer'])
# def default_cataloguer(data):
#     pass

class AssignedDescriptiveCataloguerForm(AssignedWorkerForm):
    schema = IAssignedDescriptiveCataloguer
    submitAction = 'submitDescriptiveCataloguingPreparing'
    fieldName = 'cataloguer'
    roleName = 'E-Deposit: Descriptive Cataloguer'

class AssignedDescriptiveReviewerForm(AssignedWorkerForm):
    schema = IAssignedDescriptiveReviewer
    submitAction = 'submitDescriptiveCataloguingReviewPreparing'
    fieldName = 'reviewer'
    roleName = 'E-Deposit: Descriptive Cataloguing Reviewer'
                                 
class AssignedSubjectCataloguerForm(AssignedWorkerForm):
    schema = IAssignedSubjectCataloguer
    submitAction = 'submitSubjectCataloguingPreparing'
    fieldName = 'cataloguer'
    roleName = 'E-Deposit: Subject Cataloguer'

class AssignedSubjectReviewerForm(AssignedWorkerForm):
    schema = IAssignedSubjectReviewer
    submitAction = 'submitSubjectCataloguingReviewPreparing'
    fieldName = 'reviewer'
    roleName = 'E-Deposit: Subject Cataloguing Reviewer'

class PortletFormView(FormWrapper):
     """ Form view which renders z3c.forms embedded in a portlet.
     Subclass FormWrapper so that we can use custom frame template. """
     index = ViewPageTemplateFile("formwrapper.pt")

class IAssignDescriptiveCataloguerDataProvider(IPortletDataProvider):
    pass

class IAssignDescriptiveReviewerDataProvider(IPortletDataProvider):
    pass

class IAssignSubjectCataloguerDataProvider(IPortletDataProvider):
    pass

class IAssignSubjectReviewerDataProvider(IPortletDataProvider):
    pass

class DescriptiveCataloguerAssignment(base.Assignment):
    implements(IAssignDescriptiveCataloguerDataProvider)
    def __init__(self):
        pass

    @property
    def title(self):
        return _(u"Waiting for work assignment")

Assignment = DescriptiveCataloguerAssignment

class DescriptiveReviewerAssignment(base.Assignment):
    implements(IAssignDescriptiveReviewerDataProvider)
    def __init__(self):
        pass

    @property
    def title(self):
        return _(u"Waiting for work assignment")

class SubjectCataloguerAssignment(base.Assignment):
    implements(IAssignSubjectCataloguerDataProvider)
    def __init__(self):
        pass

    @property
    def title(self):
        return _(u"Waiting for work assignment")

class SubjectReviewerAssignment(base.Assignment):
    implements(IAssignSubjectReviewerDataProvider)
    def __init__(self):
        pass

    @property
    def title(self):
        return _(u"Waiting for work assignment")


class Renderer(base.Renderer):
    """Portlet renderer.

    This is registered in configure.zcml. The referenced page template is
    rendered, and the implicit variable 'view' will refer to an instance
    of this class. Other methods can be added and referenced in the template.
    """

    render = ViewPageTemplateFile('waitingforworkassignment.pt')
    fornClass = AssignedDescriptiveCataloguerForm

    def __init__(self, context, request, view, manager, data):
        base.Renderer.__init__(self, context, request, view, manager, data)
        self.form_wrapper = self.createForm()

    def createForm(self):
        """ Create a form instance.

        @return: z3c.form wrapped for Plone 3 view
        """
        context = self.context.aq_inner
        form = self.formClass(context, self.request)

        # Wrap a form in Plone view
        view = PortletFormView(context, self.request)
        view = view.__of__(context) # Make sure acquisition chain is respected
        view.form_instance = form
        return view

class AssignDescriptiveCataloguerRenderer(Renderer):
    formClass = AssignedDescriptiveCataloguerForm
    @property
    def available(self):
        state = api.content.get_state(self.context)
        return 'descriptiveCataloguingPreparing' in state or 'descriptiveCataloguing' in state

class AssignDescriptiveReviewerRenderer(Renderer):
    formClass = AssignedDescriptiveReviewerForm
    @property
    def available(self):
        state = api.content.get_state(self.context)
        return 'descriptiveCataloguingReviewPreparing' in state or 'descriptiveCataloguingReview' in state

class AssignSubjectCataloguerRenderer(Renderer):
    formClass = AssignedSubjectCataloguerForm
    @property
    def available(self):
        state = api.content.get_state(self.context)
        return 'subjectCataloguingPreparing' in state or 'subjectCataloguing' in state

class AssignSubjectReviewerRenderer(Renderer):
    formClass = AssignedSubjectReviewerForm
    @property
    def available(self):
        state = api.content.get_state(self.context)
        return 'subjectCataloguingReviewPreparing' in state or 'subjectCataloguingReview' in state
    

# NOTE: If this portlet does not have any configurable parameters, you can
# inherit from NullAddForm and remove the form_fields variable.

class AssignDescriptiveCataloguerAddForm(base.AddForm):
    form_fields = formlib.Fields(IAssignDescriptiveCataloguerDataProvider)
    def create(self, data):
        return DescriptiveCataloguerAssignment(**data)

class AssignDescriptiveReviewerAddForm(base.AddForm):
    form_fields = formlib.Fields(IAssignDescriptiveReviewerDataProvider)
    def create(self, data):
        return DescriptiveReviewerAssignment(**data)

class AssignSubjectCataloguerAddForm(base.AddForm):
    form_fields = formlib.Fields(IAssignSubjectCataloguerDataProvider)
    def create(self, data):
        return SubjectCataloguerAssignment(**data)

class AssignSubjectReviewerAddForm(base.AddForm):
    form_fields = formlib.Fields(IAssignSubjectReviewerDataProvider)
    def create(self, data):
        return SubjectReviewerAssignment(**data)

