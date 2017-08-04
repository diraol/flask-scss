from pathlib import Path

from scss.compiler import Compiler

class Scss(object):
    '''
    Main and only class for Flask-Scss. It is in charge on the discovery of
    .scss files and compiles them every time they are modified.

    Any application that wants to use Flask-Scss must create a instance of this class
    '''

    def __init__(self, app, static_dir=None, asset_dir=None, load_paths=None):
        '''

        See :ref:`scss_discovery_rules`
        and :ref:`static_discovery_rules`
        for more information about the impact of ``static_dir`` and
        ``asset_dir`` parameters.

        Parameters here has preedence over Parameters found in the application
        config.

        :param app: Your Flask Application
        :param static_dir: The path to the ``static`` directory of your
                           application (optional)
        :param asset_dir: The path to the ``assets`` directory where Flask-Scss
                          will search ``.scss`` files (optional)
        :param load_paths: A list of folders to add to pyScss load_paths
                           (for ex., the path to a library like Compass)
        '''
        if not load_paths:
            load_paths = []

        self.app = app
        self.asset_dir = self.set_asset_dir(asset_dir)
        self.static_dir = self.set_static_dir(static_dir)
        self.assets = {}
        self.partials = {}

        load_path_list = ([self.asset_dir] if self.asset_dir else []) \
                       + (load_paths or app.config.get('SCSS_LOAD_PATHS', []))

        # pyScss.log = app.logger
        self.compiler = Compiler(search_path=load_path_list)
        if self.app.testing or self.app.debug:
            self.set_hooks()

    def set_asset_dir(self, asset_dir):
        asset_dir = asset_dir \
                    or self.app.config.get('SCSS_ASSET_DIR', None) \
                    or Path(self.app.root_path) / 'assets'

        asset_dir = Path(asset_dir)
        if not asset_dir.match('^/'):
            asset_dir = Path(self.app.root_path) / asset_dir

        if (asset_dir / 'scss').exists():
            return asset_dir / 'scss'
        elif asset_dir.exists():
            return asset_dir

        return None

    def set_static_dir(self, static_dir):
        static_dir = static_dir  \
                        or self.app.config.get('SCSS_STATIC_DIR', None) \
                        or Path(self.app.root_path) / Path(self.app.static_folder)

        static_dir = Path(static_dir)
        if not static_dir.match('^/'):
            static_dir = Path(self.app.root_path) / static_dir

        if (static_dir / 'css').exists():
            return static_dir / 'css'
        elif static_dir.exists():
            return static_dir

        return None

    def set_hooks(self):
        if self.asset_dir is None:
            self.app.logger.warning("The asset directory cannot be found."
                                    "Flask-Scss extension has been disabled")
            return
        if self.static_dir is None:
            self.app.logger.warning("The static directory cannot be found."
                                    "Flask-Scss extension has been disabled")
            return
        self.app.logger.info("Pyscss loaded!")
        self.app.before_request(self.update_scss)

    def discover_scss(self):
        for src_path in self.asset_dir.glob('**/*.scss'):
            src_path = src_path.resolve()
            filename = src_path.stem
            if filename.startswith('_') and src_path not in self.partials:
                self.partials[src_path] = src_path.stat().st_mtime
            elif src_path not in self.partials and src_path not in self.assets:
                dest_path = Path(str(src_path).replace(
                    str(self.asset_dir),
                    str(self.static_dir)).replace('.scss', '.css'))
                self.assets[src_path] = dest_path

    def partials_have_changed(self):
        res = False
        for partial, old_mtime in self.partials.items():
            cur_mtime = partial.stat().st_mtime
            if cur_mtime > old_mtime:
                res = True
                self.partials[partial] = cur_mtime
        return res

    def update_scss(self):
        self.discover_scss()
        if self.partials_have_changed():
            for asset, dest_path in self.assets.items():
                self.compile_scss(asset, dest_path)
            return
        for asset, dest_path in self.assets.items():
            exist = dest_path.exists()
            dest_mtime = dest_path.stat().st_mtime if dest_path.exists() \
                    else -1
            if asset.stat().st_mtime > dest_mtime:
                self.compile_scss(asset.resolve(), dest_path.resolve())

    def compile_scss(self, asset, dest_path):
        self.app.logger.info("[flask-pyscss] refreshing %s", dest_path)
        if not dest_path.parent.exists():
            dest_path.parent.mkdir()

        with open(dest_path, 'w') as file_out:
            with open(asset, 'r') as file_in:
                file_out.write(self.compiler.compile_string(file_in.read()))
