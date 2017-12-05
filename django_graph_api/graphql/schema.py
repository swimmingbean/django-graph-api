import copy

from graphql.ast import (
    FragmentDefinition,
    Query,
)
from graphql.parser import GraphQLParser
from django_graph_api.graphql.types import (
    BooleanField,
    CharField,
    Enum,
    ENUM,
    EnumField,
    INPUT_OBJECT,
    INTERFACE,
    LIST,
    ManyEnumField,
    ManyRelatedField,
    NON_NULL,
    Object,
    OBJECT,
    RelatedField,
    SCALAR,
    UNION,
)


class DirectiveLocationEnum(Enum):
    object_name = '__DirectiveLocation'
    values = (
        {
            'name': 'QUERY',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': 'MUTATION',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': 'FIELD',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': 'FRAGMENT_DEFINITION',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': 'FRAGMENT_SPREAD',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': 'INLINE_FRAGMENT',
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
    )


class TypeKindEnum(Enum):
    object_name = '__TypeKind'
    values = (
        {
            'name': SCALAR,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': OBJECT,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': INTERFACE,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': UNION,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': ENUM,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': INPUT_OBJECT,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': LIST,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
        {
            'name': NON_NULL,
            'description': None,
            'isDeprecated': False,
            'deprecationReason': None,
        },
    )


class InputValueObject(Object):
    object_name = '__InputValue'
    name = CharField()
    description = CharField()
    type = RelatedField(lambda: TypeObject)
    defaultValue = CharField()


class DirectiveObject(Object):
    object_name = '__Directive'
    name = CharField()
    description = CharField()
    locations = ManyEnumField(DirectiveLocationEnum)
    args = ManyRelatedField(InputValueObject)


class FieldObject(Object):
    # self.data will be an item from a declared fields dict
    object_name = '__Field'
    name = CharField()
    description = CharField()
    type = RelatedField(lambda: TypeObject)

    def get_name(self):
        return self.data[0]

    def get_description(self):
        return getattr(self.data[1], 'description', None)

    def get_type(self):
        return self.data[1].type_


class EnumValueObject(Object):
    object_name = '__EnumValue'
    name = CharField()
    description = CharField()
    isDeprecated = BooleanField()
    deprecationReason = CharField()


class TypeObject(Object):
    # self.data will be an object or scalar
    object_name = '__Type'
    kind = EnumField(TypeKindEnum)
    name = CharField()
    description = CharField()
    fields = ManyRelatedField(FieldObject)
    inputFields = ManyRelatedField(InputValueObject)
    interfaces = ManyRelatedField('self')
    enumValues = ManyRelatedField(EnumValueObject)

    def get_name(self):
        return self.data.object_name

    def get_fields(self):
        if self.data.kind != OBJECT:
            return None
        return sorted(
            self.data._declared_fields.items(),
            key=lambda item: item[0],
        )

    def get_inputFields(self):
        return []

    def get_interfaces(self):
        return None

    def get_enumValues(self):
        if self.data.kind != ENUM:
            return None

        return self.data.values


class SchemaObject(Object):
    # self.data will be the query_root.
    object_name = '__Schema'
    types = ManyRelatedField(TypeObject)
    queryType = RelatedField(TypeObject)
    mutationType = RelatedField(TypeObject)
    directives = ManyRelatedField(DirectiveObject)

    def _collect_types(self, object_type, types=None):
        if types is None:
            types = set()
        for field in object_type._declared_fields.values():
            if isinstance(field, RelatedField):
                new_object_type = field.resolve_object_type(field.object_type)
                if new_object_type == 'self':
                    continue
                if new_object_type in types:
                    continue
                types.add(new_object_type)
                self._collect_types(new_object_type, types)
            elif field.type_:
                types.add(field.type_)
        return types

    def _type_key(self, type_):
        object_name = type_.object_name
        return (
            object_name.startswith('__'),
            type_.kind,
            object_name,
        )

    def get_types(self):
        types = self._collect_types(self.data)
        return sorted(types, key=self._type_key)

    def get_queryType(self):
        return self.data

    def get_mutationType(self):
        return None

    def get_directives(self):
        return []


class Schema(object):
    """
    Required for a GraphQL API.

    A schema is a set of nodes and edges with at least one query root to access the rest of
    the schema.

    To use:
    ::

        schema = Schema()

        @schema.register_query_root
        class QueryRoot(Object):
            hello = CharField()

            def get_hello(self):
                return 'world'

    Each GraphQLView is mapped to a single schema.
    ::

        urlpatterns = [
            url(r'^graphql$', GraphQLView.as_view(schema=schema)),
        ]
    """
    def __init__(self):
        self.query_root = None

    def register_query_root(self, BaseQueryRoot):
        class QueryRoot(BaseQueryRoot):
            def get___schema(self):
                return self.__class__
        QueryRoot._declared_fields = copy.deepcopy(BaseQueryRoot._declared_fields)
        QueryRoot._declared_fields['__schema'] = RelatedField(SchemaObject)

        self.query_root = QueryRoot
        return QueryRoot

    def execute(self, document):
        """
        Queries the schema in python.

        :param document: A GraphQL query string
        :return: JSON of returned data or errors

        e.g.
        ::

            query = '''
            {
                users {
                    name
                }
            }
            '''
            schema.execute(query)

        Might return
        ::

            {
                "data": {
                    "users": [
                        {"name": "Buffy Summers"},
                        {"name": "Willow Rosenberg"},
                        {"name": "Xander Harris"}
                    ]
                }
            }
        """
        parser = GraphQLParser()
        ast = parser.parse(document)

        queries = [
            definition for definition in ast.definitions
            if isinstance(definition, Query)
        ]
        assert len(queries) == 1, "Exactly one query must be defined"

        fragments = {
            definition.name: definition
            for definition in ast.definitions
            if isinstance(definition, FragmentDefinition)
        }

        return {
            'data': self.query_root(
                ast=queries[0],
                data=None,
                fragments=fragments,
            ).serialize(),
        }


schema = Schema()
