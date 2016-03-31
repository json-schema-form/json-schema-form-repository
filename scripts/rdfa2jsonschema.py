### This script parses the N-quads of the schema.org RDF definitions into an approximate JSON Schema
### Only works in Python 2.7.x, because of a I don't know why somewhere in rdflib

import json
import rdflib
import urlparse
import os

if __name__ == '__main__':
    _script_dir = os.path.dirname(__file__)
    _schema_version = "2.2"
    _graph = rdflib.Graph()
    with open("../releases/2.2/all-layers.nq", "r") as _f:
        _graph.parse(_f, format="nquads")


    _subjects = {}
    # Group by subject
    for _ctx in _graph.store.contexts():
        print(str(_ctx))
        for _subj, _pred, _obj in _ctx:
            _curr_subj = str(_subj)
            if _curr_subj not in _subjects:
                _subjects[_curr_subj] = []
            try:
                _subjects[_curr_subj].append({"predicate":str(_pred), "object":str(_obj)})
            except:
                _subjects[_curr_subj].append({"predicate":str(_pred), "object":_obj})

    _classes = {}
    _properties = {}
    # Loop all subjects, put class definitions among class definitions and the same with properties
    for _k, _s in _subjects.items():

        for _c in _s:
            if _c["predicate"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and \
                            _c["object"] == "http://www.w3.org/2000/01/rdf-schema#Class":
                _new_class = {"parents": [], "properties": {}}

                for _curr_predicate in _s:
                    if _curr_predicate["predicate"] == "http://www.w3.org/2000/01/rdf-schema#label":
                        _new_class["name"] = _curr_predicate["object"]
                    elif _curr_predicate["predicate"] == "http://www.w3.org/2000/01/rdf-schema#comment":
                        _new_class["description"] = _curr_predicate["object"]
                    elif _curr_predicate["predicate"] == "http://www.w3.org/2000/01/rdf-schema#subClassOf":
                        _new_class["parents"].append(_curr_predicate["object"])

                _classes[_k] = _new_class
            elif _c["predicate"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and \
                            _c["object"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property":
                _new_property = {"classes": [], "types" : []}

                for _curr_predicate in _s:
                    if _curr_predicate["predicate"] == "http://www.w3.org/2000/01/rdf-schema#label":
                        _new_property["name"] = _curr_predicate["object"]
                    elif _curr_predicate["predicate"] == "http://www.w3.org/2000/01/rdf-schema#comment":
                        _new_property["description"] = _curr_predicate["object"]
                    elif _curr_predicate["predicate"] == "http://schema.org/domainIncludes":
                        _new_property["classes"].append(_curr_predicate["object"])
                    elif _curr_predicate["predicate"] == "http://schema.org/rangeIncludes":
                        _new_property["types"].append(_curr_predicate["object"])
                _properties[_k] = _new_property

    # Map properties to classes
    for _curr_propertyname, _curr_property in _properties.items():
        for _curr_class in _curr_property["classes"]:
            _classes[_curr_class]["properties"][_curr_propertyname] = _curr_property



    def recurse_parents(_class):
        # Recurse and collect parent classes' properties
        _result = {}
        for _curr_parent in _class["parents"]:
            if _curr_parent != "https://www.w3.org/2000/01/rdf-schema#Class" and \
                _curr_parent != "http://www.w3.org/2000/01/rdf-schema#Class":
                _curr_class = _classes[_curr_parent]
                _result.update(_curr_class["properties"])
                _result.update(recurse_parents(_curr_class))

        return _result

    # Add all inherited properties
    for _curr_classname, _curr_class in _classes.items():
        _curr_class["properties"].update(recurse_parents(_curr_class))

    # Loop all classes and generate JSON schema files
    for _curr_classname, _curr_class in _classes.items():
        # print ("Class: " + urlparse.urlparse(_curr_classname)[2][1:] + "(" + ", ".join(_curr_class["parents"]) + ")")
        _schema_name = urlparse.urlparse(_curr_classname)[2][1:]
        # print (_curr_class["description"])
        # print ("Properties:")
        _curr_properties = {}
        # Gather all properties
        for _curr_propertyname, _curr_property in _curr_class["properties"].items():

            _curr_parsed_propertyname = urlparse.urlparse(_curr_propertyname)[2][1:]

            _new_types = []

            # Approximate primitive types and and $refs where needed
            for _curr_type in _curr_property["types"]:
                _parsed_type = urlparse.urlparse(_curr_type)[2][1:]
                if _parsed_type in ["Text", "Date", "DateTime", "Time", "URL"]:
                    _new_types.append({
                        "type": "string"
                    })
                elif _parsed_type in ["Boolean"]:
                    _new_types.append({
                        "type": "boolean"
                    })
                elif _parsed_type in ["Number", "Integer"]:
                    _new_types.append({
                        "type": "number"
                    })

                else:
                    _new_types.append({
                        "$ref": "file://" + _parsed_type.lower() + ".json"
                    })
            _new_property = {"description" : _curr_property["description"]}
            if len(_new_types) > 1:
                _new_property["anyOf"] = _new_types
            elif len(_new_types) == 1:
                _new_property.update(_new_types[0])
            else:
                raise Exception("No type for " + _curr_parsed_propertyname)
            _curr_properties[_curr_parsed_propertyname] = _new_property
            # print("- " + _curr_parsed_propertyname + "(" + " or ".join([urlparse.urlparse(x)[2][1:] for x in _curr_property["types"]]) +  ")")

        # Actually create the schema structure
        _new_schema = {
          "$schema": "http://json-schema.org/draft-04/schema#",
          "description": _curr_class["description"],
          "title": _schema_name,
          "type": "object",
          "version": _schema_version,
          "properties": _curr_properties
        }

        _new_filename = os.path.join(_script_dir, "..", "schemas", _schema_name.lower() + ".json")
        # Write the file
        with open(_new_filename, "w") as _f:
            json.dump(_new_schema, _f)
            print("Wrote to " + os.path.abspath(_new_filename))