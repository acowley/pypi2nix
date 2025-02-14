{ stdenv, fetchurl, unzip, which, makeWrapper, python }:

let
  deps = import ./deps.nix { inherit fetchurl; };
in
  stdenv.mkDerivation {
    name = "pypi2nix-bootstrap";
    src = deps.pip;
    buildInputs = [ which python makeWrapper ];
    installPhase = ''
      mkdir -p $out/bin $out/site-packages

      mkdir index/
      cp ${deps.pipWhl} index/pip-${deps.pipVersion}-py2.py3-none-any.whl
      cp ${deps.setuptoolsWhl} index/setuptools-${deps.setuptoolsVersion}-py2.py3-none-any.whl
      cp ${deps.wheel} index/wheel-${deps.wheelVersion}.tar.gz
      cp ${deps.zcbuildout} index/zc.buildout-${deps.zcbuildoutVersion}.tar.gz
      cp ${deps.zcrecipeegg} index/zc.recipe.egg-${deps.zcrecipeeggVersion}.tar.gz

      mkdir tmp
      mv pip tmp/
      cd tmp

      ${python.interpreter} -c "import sys, pip; sys.exit(pip.main(['install', '--force-reinstall', '--upgrade', 'pip', 'setuptools', '--no-index', '--find-links=file://$PWD/../index', '-v', '--target', '$out/base']))"
      PYTHONPATH=$out/base ${python.interpreter} -c "import sys, pip; sys.exit(pip.main(['install', '--force-reinstall', '--upgrade', 'wheel', '--no-index', '--find-links=file://$PWD/../index', '-v', '--target', '$out/extra']))"
      PYTHONPATH=$out/base ${python.interpreter} -c "import sys, pip; sys.exit(pip.main(['install', '--force-reinstall', '--upgrade', 'zc.buildout', 'zc.recipe.egg', '--no-index', '--find-links=file://$PWD/../index', '-v', '--target', '$out/extra']))"
      touch $out/extra/zc/__init__.py

      echo -e "#!${python.interpreter}\nimport sys, pip; sys.exit(pip.main())" > $out/bin/pip
      echo -e "#!${python.interpreter}\nimport sys, zc.buildout.buildout\nsys.exit(zc.buildout.buildout.main())" > $out/bin/buildout

      sed -i -e "s|zinfo = zipfile.ZipInfo(path, date_time)|zinfo = zipfile.ZipInfo(path, (1980,1,1,0,0,0))|" $out/extra/wheel/archive.py
      ${python.interpreter} -m compileall -f $out/extra/wheel/archive.py

      chmod +x $out/bin/*
    '';
  }
