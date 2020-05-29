# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from data_validation import consts
from data_validation.query_builder.query_builder import QueryBuilder, GroupedField, AggregateField


class ValidationBuilder(object):
    def __init__(self, config, source_client, target_client, verbose=False):
        """ Initialize a ValidationBuilder client

            :param config: The Validation config supplied
            :param source_client: The Ibis client for the source DB
            :param target_client: The Ibis client for the target DB
            :param verbose: If verbose, the Data Validation client will print queries run
        """
        self.verbose = verbose
        self.config = config
        self.validation_type = config[consts.CONFIG_TYPE]

        self.source_client = source_client
        self.target_client = target_client

        self.source_builder = self.get_query_builder(self.validation_type)
        self.target_builder = self.get_query_builder(self.validation_type)
        
        self.aggregate_aliases = []
        self.group_aliases = []

        self.add_config_aggregates()
        self.add_config_query_groups()
        self.add_query_limit()

    @staticmethod
    def get_query_builder(validation_type):
        """ Return Query Builder object given validation type """
        if validation_type in ["Column", "GroupedColumn"]:
            builder = QueryBuilder.build_count_validator()
        else:
            msg = "Validation Builder supplied unknown type: %s" % validation_type
            raise ValueError(msg)

        return builder

    def get_config_aggregates(self):
        """ Return Aggregates from Config """
        return self.config.get(consts.CONFIG_AGGREGATES) or []

    def get_config_query_groups(self):
        """ Return Query Groups from Config """
        return self.config.get(consts.CONFIG_GROUPED_COLUMNS) or []

    def get_aggregate_aliases(self):
        """ Return List of String Aliases """
        return self.aggregate_aliases

    def get_group_aliases(self):
        """ Return List of String Aliases """
        return self.group_aliases

    def add_config_aggregates(self):
        """ Add Aggregations to Query """
        aggregate_fields = self.get_config_aggregates()
        for aggregate_field in aggregate_fields:
            self.add_aggregate(aggregate_field)

    def add_config_query_groups(self):
        """ Add Grouped Columns to Query """
        grouped_fields = self.get_config_query_groups()
        for grouped_field in grouped_fields:
            self.add_query_group(grouped_field)

    def add_aggregate(self, aggregate_field):
        """ Add Aggregate Field to Queries 

            :param aggregate_field: Dict object with source, target, and aggregation info
        """
        alias = aggregate_field[consts.CONFIG_FIELD_ALIAS]
        source_field_name = aggregate_field[consts.CONFIG_SOURCE_COLUMN]
        target_field_name = aggregate_field[consts.CONFIG_TARGET_COLUMN]
        aggregate_type = aggregate_field.get(consts.CONFIG_TYPE)

        if not hasattr(AggregateField, aggregate_type):
            raise Exception("Unknown Aggregation Type: {}".format(aggregate_type))

        source_agg = getattr(AggregateField, aggregate_type)(
            field_name=source_field_name, alias=alias
        )
        target_agg = getattr(AggregateField, aggregate_type)(
            field_name=target_field_name, alias=alias
        )

        self.source_builder.add_aggregate_field(source_agg)
        self.target_builder.add_aggregate_field(target_agg)
        self.aggregate_aliases.append(alias)


    def add_query_group(self, grouped_field):
        """ Add Grouped Field to Query

            :param grouped_field: Dict object with source, target, and cast info
        """
        alias = grouped_field[consts.CONFIG_FIELD_ALIAS]
        source_field_name = grouped_field[consts.CONFIG_SOURCE_COLUMN]
        target_field_name = grouped_field[consts.CONFIG_TARGET_COLUMN]
        cast = grouped_field.get(consts.CONFIG_CAST)

        source_field = GroupedField(
            field_name=source_field_name, alias=alias, cast=cast
        )
        target_field = GroupedField(
            field_name=target_field_name, alias=alias, cast=cast
        )

        self.source_builder.add_grouped_field(source_field)
        self.target_builder.add_grouped_field(target_field)
        self.group_aliases.append(alias)

    def get_source_query(self):
        """ Return query for source validation """
        source_config = {
            "data_client": self.source_client,
            "schema_name": self.config["schema_name"],
            "table_name": self.config["table_name"],
        }
        query = self.source_builder.compile(**source_config)
        if self.verbose:
            print("-- ** Source Query ** --")
            print(query)

        return query

    def get_target_query(self):
        """ Return query for source validation """
        target_config = {
            "data_client": self.target_client,
            "schema_name": self.config.get(
                "target_schema_name", self.config["schema_name"]
            ),
            "table_name": self.config.get(
                "target_table_name", self.config["table_name"]
            ),
        }
        query = self.target_builder.compile(**target_config)
        if self.verbose:
            print("-- ** Target Query ** --")
            print(query)

        return query

    def add_query_limit(self):
        """ Add a limit to the query results

            **WARNING** this can skew results and should be used carefully
        """
        limit = self._get_query_limit()
        self.source_builder.limit = limit
        self.target_builder.limit = limit

    def _get_query_limit(self):
        """ Return limit int value for query (Default None)

            **WARNING** this can skew results and should be used carefully
        """
        return self.config.get(consts.CONFIG_LIMIT)
