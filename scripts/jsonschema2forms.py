import json
import os
from copy import deepcopy
from urllib.parse import urlparse
import jsonschema

from jsonschema.validators import RefResolver
script_dir = os.path.dirname(__file__)
resolve_cache = {}
def general_uri_handler(_uri, _folder):
    """
    This function looks up a JSON schema that matches the URL in the given folder
    :param _uri: The _uri to handle
    :return: The schema
    """
    print("loading $ref " + _uri)
    # Use urlparse to parse the file location from the URI
    _file_location = os.path.abspath(os.path.join(_folder, urlparse(_uri).netloc))

    # noinspection PyTypeChecker
    with open(_file_location, "r", encoding="utf-8") as _schema_file:
        _json = json.load(_schema_file)

    return _json

def file_uri_handler(_uri):
    global script_dir
    return general_uri_handler(_uri=_uri, _folder=os.path.join(script_dir, "..", "schemas"))

def resolveSchema( _schema, _resolver):
    """
    Recursively resolve all I{$ref} JSON references in a JSON Schema. (taken from
    :param _schema: A L{dict} with a JSON Schema.
    :return: The resolved JSON Schema, a L{dict}.
    """
    _result = deepcopy(_schema)
    global resolve_cache

    def local_resolve(_obj, _ref_history, _level):
        """
        Recurse the JSON-tree and see where there are unresolved remote references.
        :param _obj: The node to resolve
        :param _ref_history: The previously resolved remote references, for cyclical check
        """
        _indent = (str(_level) + " " * (_level * 2))


        if _level > 3:
            return


        if isinstance(_obj, list):
            # Loop any list
            for item in _obj:
                local_resolve(item, _ref_history, _level + 1)
            return

        if isinstance(_obj, dict):

            if "$ref" in _obj:
                #print("$ref" + str(_obj))
                _curr_ref = _obj["$ref"]

                # Do not resolve local references
                if _curr_ref[0] == "#":
                    return

                # Do not resolve circular references
                if _curr_ref in _ref_history:
                    print(_indent + " Cyclical remote reference, will not resolve: " + str(_curr_ref) + ":  Formers " + str(_ref_history))
                    return

                # Cannot cache resolutions as we need circular reference checks every time
                # TODO: Could a deepcopy make caching work?
                #if _curr_ref in resolve_cache:
                #    print(_indent  + ": Using cached " + _curr_ref)
                #    _obj.update(resolve_cache[_curr_ref])
                #else:
                _resolved = file_uri_handler(_curr_ref)
                # Resolve the resolved schema
                print(_indent + "Resolving " + _curr_ref)
                local_resolve(_resolved, _ref_history + [_curr_ref], _level + 1)

                # Remove the reference
                del _obj["$ref"]
                # Add the resolved fragment to the schema
                _obj.update(_resolved)


            else:
                # Loop all properties
                for _key, _value in _obj.items():
                    print(_indent + "Key = " + _key)
                    if isinstance(_value, dict):
                        if "$ref" in _value or _key == "properties":
                            local_resolve(_value, _ref_history, _level + 1)
                        elif "oneOf" in _value:
                            # TODO: Will there ever be anyOf in schema.org?
                            # print("parsing an anyOf : " + _key + "=" + str(_value["anyOf"]))
                            for _item in _value["oneOf"]:
                                if "$ref" in _item:
                                    #print("Resolving anyOf item : " + str(_item))
                                    local_resolve(_item, _ref_history, _level + 1)


    try:
        local_resolve(_result, [], 0)
    except Exception as e:
        raise Exception("schemaTools.resolveSchema: Error resolving schema:" + str(e) + "Schema " + json.dumps(_schema, indent=4))

    #with open(os.path.join(script_dir, "..", "schemas", "resolved", _result["title"].lower() + ".json"), "w") as _f:
    #    json.dump(_result, _f)

    # Make top allOf into properties
    if "allOf" in _result:
        _new_properties = {}
        for _curr_properties in _result["allOf"]:
            _new_properties.update(_curr_properties["properties"])

        _result["properties"] = _new_properties
        del _result["allOf"]

    _result["$schema"] = "http://json-schema.org/draft-04/schema#"


    try:
        jsonschema.validators.Draft4Validator({}, resolver=_resolver).check_schema(_result)
        pass
    except Exception as e:
        raise Exception("schemaTools.resolveSchema: error validating resolved schema:" + str(e) + "Schema " + json.dumps(_result, indent=4))

    return _result

def property2form(_property_name, _property):

    if isinstance(_property, dict):

        if "description" not in _property:
            if _property_name == "items":
                _description = "An array item. (generated name)"
            else:
                _description = "Not available"
        else:
            _description = _property["description"]

        if "type" in _property:
            _curr_key = {"key": _property_name, "description": _description}
            _curr_type = _property["type"]
            if _curr_type in ["string"]:
                _curr_key["type"] = "text"
            elif _curr_type in ["number", "integer"]:
                _curr_key["type"] = "number"
            elif _curr_type in ["boolean"]:
                _curr_key["type"] = "checkbox"
            elif _curr_type in ["array"]:
                _curr_key["type"] = "array"
                _curr_key["items"] = properties2form(_property["items"], _property_name + "[].")
            elif _curr_type in ["object"]:
                _curr_key["type"] = "fieldset"
                _curr_key["items"] = properties2form(_property["properties"], _property_name + ".")

            return _curr_key

        elif "oneOf" in _property:

            return {"key": _property_name, "type": "text",
                          "description": "Set to a plain text input as oneOf isn't currently implemented in the standard."
                                         " Description: " + _description}

        elif "$ref" in _property:
            return {"key": _property_name, "type": "text",
                    "description": "Set to a plain text input as $ref:ed type(" + _property["$ref"] + ") isn't resolved."
                                   " Description: " + _description}

    return {}

def properties2form(_properties, _prefix = ""):
    _form = []

    for _curr_property_name, _curr_property in _properties.items():
        _form.append(property2form(_prefix + _curr_property_name, _curr_property))

    return _form


if __name__ == '__main__':

    _schema_dir = os.path.join(script_dir, "..", "schemas")
    _schema_dir_list = os.listdir(_schema_dir)

    _resolver = RefResolver(base_uri="",
                                handlers={"file": file_uri_handler}, referrer=None, cache_remote=False)

    for _curr_file in _schema_dir_list:
        if os.path.splitext(_curr_file)[1] == ".json":
            with open(os.path.join(_schema_dir, _curr_file)) as _f_def:
                _curr_schema = json.load(_f_def)

            _resolved_schema = resolveSchema(_curr_schema, _resolver)
            _new_form = properties2form(_resolved_schema["properties"])
            with open(os.path.join(script_dir, "..", "schemas", "resolved", "forms", _resolved_schema["title"].lower() + "-form.json"),
                      "w") as _f:
                json.dump(_new_form, _f)

            print(_curr_schema["title"] + " checked out ok.")
            #_form = []
            #for _curr_property in _curr_schema:
            #    pass

