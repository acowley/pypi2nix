import sys
import os
import click


DEFAULT_NIX = '''# generated using pypi2nix tool (version: %(version)s)
# See more at: https://github.com/garbas/pypi2nix
#
# COMMAND:
#   pypi2nix %(command_arguments)s
#

{ pkgs ? import <nixpkgs> {}
}:

let

  inherit (pkgs.stdenv.lib) fix' extends inNixShell;

  pythonPackages = pkgs.%(python_version)sPackages;
  commonBuildInputs = %(extra_build_inputs)s;
  commonDoCheck = %(enable_tests)s;

  buildEnv = { pkgs ? {}, modules ? {} }:
    let
      interpreter = pythonPackages.python.buildEnv.override {
        extraLibs = (builtins.attrValues pkgs) ++ (builtins.attrValues modules);
      };
    in {
      mkDerivation = pythonPackages.buildPythonPackage;
      interpreter = if inNixShell then interpreter.env else interpreter;
      overrideDerivation = drv: f: pythonPackages.buildPythonPackage (drv.drvAttrs // f drv.drvAttrs);
      pkgs_top_level = builtins.filter (x: !(builtins.hasAttr "top_level" x.passthru)) (
          builtins.attrValues (builtins.removeAttrs pkgs ["__unfix__"]));
      inherit buildEnv pkgs modules;
    };

  generated = import %(generated_file)s { inherit pkgs python commonBuildInputs commonDoCheck; };
  overrides = import %(overrides_file)s { inherit pkgs python; };

  python = buildEnv {
    pkgs = fix' (extends overrides generated);
  };

in python
'''

GENERATED_NIX = '''# generated using pypi2nix tool (version: %s)
#
# COMMAND:
#   pypi2nix %s
#

{ pkgs, python, commonBuildInputs ? [], commonDoCheck ? false }:

self: {
%s
}
'''

GENERATED_PACKAGE_NIX = '''
  "%(name)s" = python.mkDerivation {
    name = "%(name)s-%(version)s";
    src = pkgs.fetchurl {
      url = "%(url)s";
      %(hash_type)s= "%(hash_value)s";
    };
    doCheck = commonDoCheck;
    buildInputs = commonBuildInputs;
    propagatedBuildInputs = %(propagatedBuildInputs)s;
    meta = with pkgs.stdenv.lib; {
      homepage = "%(homepage)s";
      license = %(license)s;
      description = "%(description)s";
    };
    passthru.top_level = %(top_level)s;
  };
'''

OVERRIDES_NIX = '''
{ pkgs, python }:

self: super: {
%s
}
'''


def find_license(item):
    license = item.get('license')
    if license == 'ZPL 2.1':
        license = "licenses.zpt21"
    elif license in ['MIT', 'MIT License']:
        license = "licenses.mit"
    elif license in ['BSD', 'BSD License', 'BSD-like', 
                     'BSD or Apache License, Version 2.0'] or \
            license.startswith('BSD -'):
        license = "licenses.bsdOriginal"
    elif license in ['Apache 2.0', 'Apache License 2.0']:
        license = "licenses.asl20"
    elif license in ['GNU Lesser General Public License (LGPL), Version 3']:
        license = "licenses.lgpl3"
    elif license in ['Python Software Foundation License']:
        license = "licenses.psfl"
    elif license is None:
        license = '""'
    else:
        click.echo(
            "WARNING: Couldn't recognize license `{}` for `{}`".format(
                license, item.get('name')))
        license = '"' + license + '"'

    return license


def main(packages_metadata,
         requirements_name,
         requirements_files,
         extra_build_inputs,
         enable_tests,
         python_version,
         top_level,
         ):
    '''Create Nix expressions.
    '''

    project_folder = os.path.dirname(requirements_files[0])

    default_file = os.path.join(project_folder, '{}.nix'.format(requirements_name))
    generated_file = os.path.join(project_folder, '{}_generated.nix'.format(requirements_name))
    overrides_file = os.path.join(project_folder, '{}_override.nix'.format(requirements_name))

    version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
    with open(version_file) as f:
        version = f.read()

    metadata_by_name = {x['name'].lower(): x for x in packages_metadata}

    generated_packages_metadata = []
    for item in sorted(packages_metadata, key=lambda x: x['name']):
        propagatedBuildInputs = '[ ]'
        if item.get('deps'):
            deps = [x for x in item['deps'] if x.lower() in metadata_by_name.keys()]
            if deps:
                propagatedBuildInputs = "[\n%s\n    ]" % (
                    '\n'.join(sorted(['      self."%s"' % (
                        metadata_by_name[x.lower()]['name']) for x in deps])))
        generated_packages_metadata.append(dict(
            name=item.get("name", ""),
            version=item.get("version", ""),
            url=item.get("url", ""),
            hash_type=item['hash_type'],
            hash_value=item['hash_value'],
            propagatedBuildInputs=propagatedBuildInputs,
            homepage=item.get("homepage", ""),
            license=find_license(item),
            description=item.get("description", ""),
            top_level=str(item['name'] in top_level).lower(),
        ))

    generated = GENERATED_NIX % (
        version, ' '.join(sys.argv[1:]), '\n\n'.join(
            GENERATED_PACKAGE_NIX % x for x in generated_packages_metadata))

    overrides = OVERRIDES_NIX % ""

    default = DEFAULT_NIX % dict(
        version=version,
        command_arguments=' '.join(sys.argv[1:]),
        python_version=python_version,
        extra_build_inputs=extra_build_inputs
            and "with pkgs; [ %s ]" % (' '.join(extra_build_inputs))
            or "[]",
        generated_file='.' + generated_file[len(project_folder):],
        overrides_file='.' + overrides_file[len(project_folder):],
        enable_tests=str(enable_tests).lower(),
    )

    with open(generated_file, 'w+') as f:
        f.write(generated.strip())
        click.echo('|-> writing %s' % generated_file)

    if not os.path.exists(overrides_file):
        with open(overrides_file, 'w+') as f:
            f.write(overrides.strip())
            click.echo('|-> writing %s' % overrides_file)

    with open(default_file, 'w+') as f:
        f.write(default.strip())
