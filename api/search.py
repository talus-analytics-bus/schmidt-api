##
# # API schema
##

# Standard libraries
import re
# from collections import defaultdict

# Third party libraries
import pprint
from pony.orm import select, db_session, raw_sql, distinct, count
from flask import send_file

# Local libraries
from .db_models import db

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)


def get_matching_instances(
    to_check,
    items,
    search_text,
    explain_results: bool = True
):
    # prepare output dictionary of format:
    # {
    #   "Author": [
    #     {
    #       "id": 2,
    #       "authoring_organization": "Department of Health and Human Services",
    #       "n_items": 42,
    #       "snippets": {
    #         "authoring_organization": [
    #           "Department of <highlight>Health</highlight> and Human Services"
    #         ]
    #       }
    #     },
    #     {
    #       "id": 11,
    #       "authoring_organization": "World Health Organization",
    #       "n_items": 1,
    #       "snippets": {
    #         "authoring_organization": [
    #           "World <highlight>Health</highlight> Organization"
    #         ]
    #       }
    #     }
    #   ],
    #   ...
    # }
    matching_instances = dict()

    # for each entity to check for matches
    for class_name in to_check:

        # e.g., "exact-insensitive"
        match_type = to_check[class_name]['match_type']

        # special case: key topics, which are data field values, not entities
        # TODO modularize, reuse code
        if class_name != 'Key_Topic':
            matching_instances[class_name] = list()
            entity = getattr(db, class_name)
            matches = list()
            if match_type not in ('exact-insensitive',):
                raise NotImplementedError(
                    'Unsupported match type: ' + match_type
                )
            else:
                # for each field to check, collect the matching entities into
                # a single list `all_matches_tmp`
                fields = to_check[class_name]['fields']
                cur_search_text = search_text.lower()
                all_matches_tmp = set()
                for field in fields:

                    # get pool of entities from filtered items
                    pool = select(
                        k
                        for i in items
                        for k in getattr(i, class_name.lower() + 's')
                    )

                    # get entities that match search string
                    matches = select(
                        m for m in pool
                        if cur_search_text in getattr(m, field).lower()
                    )
                    all_matches_tmp = all_matches_tmp | set(matches[:][:])

                # for each match in the list, count number of results (slow?)
                # and get snippets showing why the instance matched
                items_query = to_check[class_name]['items_query']
                all_matches = list()
                for match in all_matches_tmp:
                    # get number of results for this match
                    n_items = count(items.filter(items_query(match)))
                    d = match.to_dict(only=(['id'] + fields))
                    d['n_items'] = n_items
                    if explain_results:
                        # exact-insensitive snippet
                        # TODO code for finding other types of snippets
                        # TODO score by relevance
                        # TODO add snippet length constraints
                        snippets = dict()
                        pattern = re.compile(cur_search_text, re.IGNORECASE)

                        def repl(x):
                            return '<highlight>' + x.group(0) + '</highlight>'
                        for field in fields:
                            snippets[field] = list()
                            if search_text in getattr(match, field).lower():
                                snippet = re.sub(
                                    pattern, repl, getattr(match, field))
                                snippets[field].append(snippet)
                        d['snippets'] = snippets
                    all_matches.append(d)
                matching_instances[class_name] = all_matches
                matching_instances[class_name].sort(key=lambda x: x[field])
        else:
            # search through all used values for matches, then return
            all_vals = select(i.key_topics.name for i in items)[:][:]
            if match_type not in ('exact-insensitive',):
                raise NotImplementedError(
                    'Unsupported match type: ' + match_type
                )
            else:
                all_matches_tmp = [
                    i for i in all_vals if cur_search_text in i.lower()
                ]
                all_matches = list()
                items_query = to_check[class_name]['items_query']
                for match in all_matches_tmp:
                    # get number of results for this match
                    n_items = count(items.filter(items_query(match)))
                    d = {'name': match}
                    d['n_items'] = n_items

                    # exact-insensitive snippet
                    # TODO code for finding other types of snippets
                    # TODO score by relevance
                    # TODO add snippet length constraints
                    if explain_results:
                        snippets = dict()
                        pattern = re.compile(cur_search_text, re.IGNORECASE)

                        def repl(x):
                            return '<highlight>' + x.group(0) + '</highlight>'
                        for field in fields:
                            snippets[field] = list()
                            if search_text in match.lower():
                                snippet = re.sub(
                                    pattern, repl, match)
                                snippets[field].append(snippet)
                        d['snippets'] = snippets
                    all_matches.append(d)
                matching_instances[class_name] = all_matches
                matching_instances[class_name].sort(key=lambda x: x[field])
    return matching_instances
