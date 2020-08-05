"""Autoupdate older conda dependencies in the requirements section."""
from __future__ import absolute_import

import re
import xml.etree.ElementTree as ET
import planemo.conda

def autoupdate(tool_path):
    """
    Autoupdate an XML file
    """
    xml_tree = ET.parse(tool_path)
    requirements = find_requirements(xml_tree)

    for macro_import in requirements['imports']:
        # recursively check macros
        macro_requirements = autoupdate('/'.join(tool_path.split('/')[:-1] + [macro_import]))
        for requirement in macro_requirements:
            if requirement not in requirements:
                requirements[requirement] = macro_requirements[requirement]

    if not requirements.get('@TOOL_VERSION@'):
        return requirements
    # check main_req is up-to-date; if so, finish without changes
    updated_main_req = get_latest_versions({requirements.get('main_req'): requirements.get('@TOOL_VERSION@')})
    if updated_main_req[requirements.get('main_req')] == requirements.get('@TOOL_VERSION@'):
        return requirements

    # if main_req is not up-to-date, update everything
    updated_version_dict = get_latest_versions(requirements.get('other_reqs'))
    update_requirements(tool_path, xml_tree, updated_version_dict, updated_main_req)
    return requirements

def find_requirements(xml_tree):
    """
    Get all requirements with versions as a dictionary of the form
    {'main_req': main requirement, 'other_reqs': {req1: version, ... },
        'imports: ['macros.xml'], '*VERSION@': '...'}
    """
    requirements = {'other_reqs': {}, 'imports': []}

    # get tokens
    for token in xml_tree.iter("token"):
        if 'VERSION@' in token.attrib.get('name', ''):
            requirements[token.attrib['name']] = token.text
    for macro_import in xml_tree.iter("import"):
        requirements['imports'].append(macro_import.text)

    # get requirements
    for requirement in xml_tree.iter("requirement"):
        if requirement.attrib.get('version') == '@TOOL_VERSION@':
            requirements['main_req'] = requirement.text
        else:
            requirements['other_reqs'][requirement.text] = requirement.attrib.get('version')
    return requirements


def get_latest_versions(version_dict):
    """
    Update a dict with current conda versions for tool requirements
    """
    for package in version_dict.keys():
        target = planemo.conda.conda_util.CondaTarget(package)
        search_results = planemo.conda.best_practice_search(target)
        version_dict[package] = search_results[0]['version']
    return version_dict


def update_requirements(tool_path, xml_tree, updated_version_dict, updated_main_req):
    """
    Update requirements to latest conda versions
    and update version tokens
    """

    tags_to_update = {'tokens': [], 'requirements': []}

    for token in xml_tree.iter("token"):
        if token.attrib.get('name') == '@TOOL_VERSION@':
            token.text = updated_main_req.values()[0]
        elif token.attrib.get('name') == '@GALAXY_VERSION@':
            token.text = '0'
        else:
            continue
        tags_to_update['tokens'].append(ET.tostring(token).strip())

    for requirement in xml_tree.iter("requirement"):
        if requirement.text not in updated_main_req:
            requirement.set('version', updated_version_dict[requirement.text])
        tags_to_update['requirements'].append(ET.tostring(requirement).strip())
    write_to_xml(tool_path, xml_tree, tags_to_update)
    return xml_tree


def write_to_xml(tool_path, xml_tree, tags_to_update):
    """
    Write modified XML to tool_path
    """
    with open(tool_path, 'r+') as f:
        xml_text = f.read()

        for token in tags_to_update['tokens']:
            xml_text = re.sub('{}>.*<{}'.format(*re.split('>.*<', token)), token, xml_text)

        for requirement in tags_to_update['requirements']:
            xml_text = re.sub('{}version=".*"{}'.format(*re.split('version=".*"', requirement)), requirement, xml_text)

        f.seek(0)
        f.truncate()
        f.write(xml_text)


__all__ = (
    "autoupdate"
)