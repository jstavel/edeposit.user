# -*- coding: utf-8 -*-
from five import grok
from plone.directives import dexterity, form
from z3c.relationfield.schema import RelationChoice, Relation, RelationList
from plone.formwidget.contenttree import ObjPathSourceBinder, PathSourceBinder
from z3c.form import field, button, validator
from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from decimal import Decimal
from plone.dexterity.content import Container
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable

from plone.supermodel import model
from Products.Five import BrowserView
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent

from edeposit.user import MessageFactory as _
from plone import api

# Interface class; used to define content-type schema.

class IProducentFolder(model.Schema, IImageScaleTraversable):
    """
    E-Deposit - folder for producents
    """

class ProducentFolder(Container):
    # Add your class methods and properties here
    def getDefaultProducentForCurrentUser(self):
        return 'key01'

    def getProducentsForCurrentUser(self):
        result = (('key01','Title 01'),('key02','Title 02'))
        currentUser = api.user.get_current()
        from plone.api.exc import UserNotFoundError
        try:
            if 'Manager' in api.user.get_roles(currentUser.id):
                brains=api.portal.get_tool('portal_catalog')(portal_type="edeposit.user.producent",sort_limit=5)
                return [ (bb['id'],bb['Title']) for bb in brains ]
        except UserNotFoundError:
            pass

        query = currentUser.id
        brains = api.portal.get_tool('portal_catalog')(portal_type="edeposit.user.producent", getAssignedProducentEditors = query)
        return [ (bb['id'],bb['Title']) for bb in brains ]

    def handleOhlaseniPublikace(self,*args,**kwargs):
        request = self.REQUEST
        path = request.physicalPathFromURL(request.URL)
        try:
            producentsIndex = path.index('producents')
            producentsPath = mainPath[producentsIndex:-1]
        except ValueError:
            pass
        currentUser = api.user.get_current()
        path="/".join(["",'producents',kwargs['nakladatel']])
        producent = api.content.get(path=path)
        epublicationFolder = producent['epublications']
        kwargs.keys()
        import pdb; pdb.set_trace()
        valuesPairs = [('vazba','online'),('nakladatel_vydavatel',producent.title),('zpracovatel_zaznamu',currentUser.id),('cena',kwargs['cena-v-kc'] and Decimal(kwargs['cena-v-kc']))]
        pairs = [('title','nazev-publikace'),('podnazev','podnazev'),('isbn_souboru_publikaci','isbn-souboru-publikaci'),('cast','cast-dil'),('nazev_casti','nazev-casti-dilu'),('rok_vydani','rok-vydani'),('poradi_vydani','poradi-vydani'),('misto_vydani','misto-vydani'),('vydano_v_koedici_s','vydano-v-koedici'),('is_public','publikace-je-verejna'),('offer_to_riv','zpristupnit-pro-riv'),]
        newEPublication = createContentInContainer(epublicationFolder,'edeposit.content.epublication',**dict([ (ii[0],kwargs.get(ii[1])) for ii in pairs] + valuesPairs))
        pass
    pass


class WorklistCSV(BrowserView):
    """Export the worklist to CSV as a one-off
    """
    
    filename = ""
    collection_name = ""
    separator = "\t"
    titles = [u"Název", 
              u"Nakladatel/vydavatel",
              u"Linka v E-Deposit "]

    def getRowValues(self,obj):
        row =  [obj.getParentTitle or "", 
                obj.getNakladatelVydavatel or "",
                obj.getURL() or ""]
        return row

    def __call__(self):
        self.request.response.setHeader("Content-type","text/csv")
        self.request.response.setHeader("Content-disposition","attachment;filename=%s.csv" % self.filename)
        header = self.separator.join(self.titles)

        def result(brain):
            return self.separator.join(self.getRowValues(brain))

        results = map(result, self.context[self.collection_name].results(batch=False))
        csvData = "\n".join([header,] + results)
        return csvData

class WorklistWaitingForUserView(WorklistCSV):
    """ this view takes userid from request and specializes collection name this way:
    originalfiles-waiting-for-user-USER_ID"""
    filename = "worklist-waiting-for-user"
    prefix_of_collection_name = "originalfiles-waiting-for-user"

    @property
    def collection_name(self):
        userid= self.request.get('userid',"")
        name = WorklistWaitingForUserView.prefix_of_collection_name + "-" + userid
        return name

class WorklistWaitingForISBNGenerationView(WorklistCSV):
    filename = "worklist-waiting-for-isbn-generation"
    collection_name = "originalfiles-waiting-for-isbn-generation"

class WorklistWaitingForAleph(WorklistCSV):
    filename = "worklist-waiting-for-aleph"
    collection_name = "originalfiles-waiting-for-aleph"

class WorklistWaitingForAcquisitionView(WorklistCSV):
    filename = "worklist-waiting-for-acquisition"
    collection_name = "originalfiles-waiting-for-acquisition"

class WorklistWaitingForISBNSubjectValidationView(WorklistCSV):
    filename = "worklist-waiting-for-isbn-subject-validation"
    collection_name = "originalfiles-waiting-for-isbn-subject-validation"

class WorklistWaitingForDescriptiveCataloguingPreparingView(WorklistCSV):
    filename = "worklist-waiting-for-descriptive-cataloguing-preparing"
    collection_name = "originalfiles-waiting-for-descriptive-cataloguing-preparing"

class WorklistWaitingForDescriptiveCataloguingReviewPreparingView(WorklistCSV):
    filename = "worklist-waiting-for-descriptive-cataloguing-review-preparing"
    collection_name = "originalfiles-waiting-for-descriptive-cataloguing-review-preparing"

class WorklistWaitingForSubjectCataloguingPreparingView(WorklistCSV):
    filename = "worklist-waiting-for-subject-cataloguing-preparing"
    collection_name = "originalfiles-waiting-for-subject-cataloguing-preparing"

class WorklistWaitingForSubjectCataloguingReviewPreparingView(WorklistCSV):
    filename = "worklist-waiting-for-subject-cataloguing-review-preparing"
    collection_name = "originalfiles-waiting-for-subject-cataloguing-review-preparing"


from edeposit.content.originalfile import IOriginalFile

@grok.provider(IContextSourceBinder)
def availableDescriptiveCataloguers(context):
    acl_users = getToolByName(context, 'acl_users')
    group = acl_users.getGroupById('Descriptive Cataloguers')
    terms = []

    if group is not None:
        for member_id in group.getMemberIds():
            user = acl_users.getUserById(member_id)
            if user is not None:
                member_name = user.getProperty('fullname') or member_id
                terms.append(SimpleVocabulary.createTerm(member_id, str(member_id), member_name))

    return SimpleVocabulary(terms)

@grok.provider(IContextSourceBinder)
def availableOriginalFiles(context):
    path = '/'.join(context.getPhysicalPath())
    query = { 
        "portal_type" : "edeposit.content.originalfile",
    }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

from edeposit.content import MessageFactory as _


# Interface class; used to define content-type schema.

class IDescriptiveCatalogizationWorkPlan(form.Schema):
    """
    E-Deposit: Catalogization Work Plan
    """

    related_catalogizator = schema.Choice( title=u"Pracovník jmenné katalogizace",
                                           required = True,
                                           source = availableDescriptiveCataloguers )
    
    assigned_originalfiles = RelationList(
        title=u"Dokumenty ke zpracování",
        required = False,
        default = [],
        value_type =   RelationChoice( 
            title=u"Originály",
            source = ObjPathSourceBinder(object_provides=IOriginalFile.__identifier__)
        )
    )
    
# @form.default_value(field=ICatalogizationWorkPlan['related_catalogizator'])
# def defaultCatalogizator(data):
#     return "jans"

class DescriptiveCatalogizationAssignForm(form.SchemaForm):
    grok.name("descriptive-cataloguers-assign")
    grok.require("cmf.ReviewPortalContent")
    grok.context(IProducentFolder)
    schema = IDescriptiveCatalogizationWorkPlan
    ignoreContext = True
    label = u""
    description = u""

    @button.buttonAndHandler(u'Přidělit práci')
    def handleOK(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        
    pass

