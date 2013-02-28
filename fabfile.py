import os

from fabric.api import *

root = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))


def pack():
    local('python setup.py sdist --formats=gztar', capture=False)


def deploy():
    local('python setup.py register -r semio sdist upload -r semio')

    dist = local('python setup.py --fullname', capture=True).strip()

    package_name, version = dist.split('-')

    rebase(version)


def rebase(version=None):
    with cd(env.root):
        dist = local('python setup.py --fullname', capture=True).strip()

        package_name, current_version = dist.split('-')

        if not version:
            version = current_version

        run('source .env/bin/activate && pip install --upgrade %s==%s' % (package_name, version))


def install(install_data=False):
    dist = local('python setup.py --fullname', capture=True).strip()

    # upload the source tarball to the temporary folder on the server
    put('dist/%s.tar.gz' % dist, '/tmp/gplab.tar.gz')

    # create a place where we can unzip the tarball, then enter
    # that directory and unzip it
    run('mkdir /tmp/gplab')

    with cd('/tmp/gplab'):
        run('tar xzf /tmp/gplab.tar.gz')

        with cd('/tmp/gplab/%s' % dist):
            # now setup the package with our virtual environment's
            # python interpreter
            run('%s/.env/bin/python setup.py install' % env.root)

            if install_data:
                run('%s/.env/bin/python setup.py install_data' % env.root)

    # now that all is set up, delete the folder again
    run('rm -rf /tmp/gplab /tmp/gplab.tar.gz')


def install_data():
    dist = local('python setup.py --fullname', capture=True).strip()

    # upload the source tarball to the temporary folder on the server
    put('dist/%s.tar.gz' % dist, '/tmp/gplab.tar.gz')

    # create a place where we can unzip the tarball, then enter
    # that directory and unzip it
    run('rm -rf /tmp/gplab')
    run('mkdir /tmp/gplab')

    with cd('/tmp/gplab'):
        run('tar xzf /tmp/gplab.tar.gz')

        with cd('/tmp/gplab/%s' % dist):
            # now setup the package with our virtual environment's
            # python interpreter
            run('%s/.env/bin/python setup.py install_data' % env.root)


def reload():
    run('kill -HUP $(cat %s)' % os.path.join(env.root, 'gunicorn_gplab.pid'))


def restart():
    sudo('sudo supervisorctl -c /etc/supervisord_tools.conf restart gplab')


def build_translations():
    package_dir = os.path.join(root, 'gplab')

    local('cd %s; pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot .' % package_dir)


def init_translations():
    package_dir = os.path.join(root, 'gplab')

    from gplab.app import app

    langs = app.config['SUBDOMAINS'].values()

    for lang in langs:
        local('cd %s; pybabel init -i messages.pot -d translations -l %s' % (package_dir, lang))


def update_translations():
    package_dir = os.path.join(root, 'gplab')

    local('cd %s; pybabel update -i messages.pot -d translations' % package_dir)


def compile_translations():
    package_dir = os.path.join(root, 'gplab')

    local('cd %s; pybabel compile -d translations' % package_dir)
