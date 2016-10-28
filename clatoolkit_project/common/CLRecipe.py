__author__ = 'Koji Nishimoto'
__date__ = '05/10/2016'


class CLRecipe(object):
    # Platform names
    PLATFORM_TWITTER = 'Twitter'
    PLATFORM_FACEBOOK = 'Facebook'
    PLATFORM_YOUTUBE = 'YouTube'
    PLATFORM_FORUM = 'Forum'
    PLATFORM_DIIGO = 'Diigo'
    PLATFORM_BLOG = 'Blog'
    PLATFORM_GITHUB = 'GitHub'
    PLATFORM_TRELLO = 'Trello'
    PLATFORM_WORDPRESS = "WordPress"

    # Verbs
    VERB_CREATED = 'created'
    VERB_SHARED = 'shared'
    VERB_LIKED = 'liked'
    VERB_RATED = 'rated'
    VERB_COMMENTED = 'commented'
    VERB_ADDED = 'added'
    VERB_UPDATED = 'updated'
    VERB_REMOVED = 'removed'
    VERB_DELETED = 'deleted'
    VERB_OPENED = 'opened'
    VERB_CLOSED = 'closed'

    # Objects
    OBJECT_NOTE = 'Note'
    OBJECT_TAG = 'Tag'
    OBJECT_ARTICLE = 'Article'
    OBJECT_VIDEO = 'Video'
    OBJECT_BOOKMARK = 'Bookmark'
    OBJECT_COLLECTION = 'Collection'
    OBJECT_FILE = 'File'
    OBJECT_TASK = 'Task'
    OBJECT_CHECKLIST = 'Checklist'
    OBJECT_CHECKLIST_ITEM = 'Checklist-item'
    OBJECT_PERSON = 'Person'

    VERB_IRI_MAPPER = {
        VERB_CREATED: 'http://www.w3.org/ns/activitystreams#Create',
        VERB_SHARED: 'http://activitystrea.ms/schema/1.0/share',
        VERB_LIKED: 'http://activitystrea.ms/schema/1.0/like',
        VERB_RATED: 'http://id.tincanapi.com/verb/rated',
        VERB_COMMENTED: 'http://adlnet.gov/expapi/verbs/commented',
        VERB_ADDED: 'http://www.w3.org/ns/activitystreams#Add',
        VERB_UPDATED: 'http://activitystrea.ms/schema/1.0/update',
        VERB_REMOVED: 'http://activitystrea.ms/schema/1.0/remove',
        VERB_DELETED: 'http://www.w3.org/ns/activitystreams#Delete',
        VERB_OPENED: 'http://activitystrea.ms/schema/1.0/open',
        VERB_CLOSED: 'http://activitystrea.ms/schema/1.0/close',
    }

    OBJECT_IRI_MAPPER = {
        OBJECT_NOTE: 'http://activitystrea.ms/schema/1.0/note',
        OBJECT_TAG: 'http://id.tincanapi.com/activitytype/tag',
        OBJECT_ARTICLE: 'http://activitystrea.ms/schema/1.0/article',
        OBJECT_VIDEO: 'http://activitystrea.ms/schema/1.0/video',
        OBJECT_BOOKMARK: 'http://activitystrea.ms/schema/1.0/bookmark',
        OBJECT_COLLECTION: 'http://activitystrea.ms/schema/1.0/collection',
        OBJECT_FILE: 'http://activitystrea.ms/schema/1.0/file',
        OBJECT_TASK: 'http://activitystrea.ms/specs/json/schema/activity-schema.html#task',
        OBJECT_CHECKLIST: 'http://id.tincanapi.com/activitytype/checklist',
        OBJECT_CHECKLIST_ITEM: 'http://id.tincanapi.com/activitytype/checklist-item'
    }

    @classmethod
    def get_verb_iri(self, verb):
        return self.VERB_IRI_MAPPER.get(verb)

    @classmethod
    def get_object_iri(self, obj):
        return self.OBJECT_IRI_MAPPER.get(obj)
