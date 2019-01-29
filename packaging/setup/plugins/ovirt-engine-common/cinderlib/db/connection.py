#
# ovirt-engine-setup -- ovirt engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""Cinderlib connection plugin."""


import gettext

from otopi import plugin
from otopi import util

from ovirt_engine import configfile

from ovirt_engine_setup import constants as osetupcons
from ovirt_engine_setup.cinderlib import constants as oclcons
from ovirt_engine_setup.engine import constants as oenginecons
from ovirt_engine_setup.engine import vdcoption
from ovirt_engine_setup.engine_common import database


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Cinderlib connection plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.HOST,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.PORT,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.SECURED,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.SECURED_HOST_VALIDATION,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.USER,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.PASSWORD,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.DATABASE,
            None
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.DUMPER,
            oenginecons.Defaults.DEFAULT_DB_DUMPER
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.FILTER,
            oenginecons.Defaults.DEFAULT_DB_FILTER
        )
        self.environment.setdefault(
            oclcons.CinderlibDBEnv.RESTORE_JOBS,
            oenginecons.Defaults.DEFAULT_DB_RESTORE_JOBS
        )

        self.environment[oclcons.CinderlibDBEnv.CONNECTION] = None
        self.environment[oclcons.CinderlibDBEnv.STATEMENT] = None
        self.environment[oclcons.CinderlibDBEnv.NEW_DATABASE] = True
        self.environment[oclcons.CinderlibDBEnv.NEED_DBMSUPGRADE] = False
        self.environment[oclcons.CinderlibDBEnv.JUST_RESTORED] = False

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        name=oclcons.Stages.DB_CL_CONNECTION_SETUP,
        condition=lambda self: self.environment[
            osetupcons.CoreEnv.ACTION
        ] != osetupcons.Const.ACTION_PROVISIONDB,
    )
    def _setup(self):
        dbovirtutils = database.OvirtUtils(
            plugin=self,
            dbenvkeys=oclcons.Const.CINDERLIB_DB_ENV_KEYS,
        )
        dbovirtutils.detectCommands()

        config = configfile.ConfigFile([
            oenginecons.FileLocations.OVIRT_ENGINE_SERVICE_CONFIG_DEFAULTS,
            oenginecons.FileLocations.OVIRT_ENGINE_SERVICE_CONFIG
        ])
        if config.get('CINDERLIB_DB_PASSWORD'):
            try:
                dbenv = {}
                for e, k in (
                    (oclcons.CinderlibDBEnv.HOST, 'CINDERLIB_DB_HOST'),
                    (oclcons.CinderlibDBEnv.PORT, 'CINDERLIB_DB_PORT'),
                    (oclcons.CinderlibDBEnv.USER, 'CINDERLIB_DB_USER'),
                    (oclcons.CinderlibDBEnv.PASSWORD,
                     'CINDERLIB_DB_PASSWORD'),
                    (oclcons.CinderlibDBEnv.DATABASE,
                     'CINDERLIB_DB_DATABASE'),
                ):
                    dbenv[e] = config.get(k)
                for e, k in (
                    (oclcons.CinderlibDBEnv.SECURED,
                     'CINDERLIB_DB_SECURED'),
                    (
                        oclcons.CinderlibDBEnv.SECURED_HOST_VALIDATION,
                        'CINDERLIB_DB_SECURED_VALIDATION'
                    )
                ):
                    dbenv[e] = config.getboolean(k)

                dbovirtutils.tryDatabaseConnect(dbenv)
                self.environment.update(dbenv)
                self.environment[
                    oclcons.CinderlibDBEnv.NEW_DATABASE
                ] = dbovirtutils.isNewDatabase()

                self.environment[
                    oclcons.CinderlibDBEnv.NEED_DBMSUPGRADE
                ] = dbovirtutils.checkDBMSUpgrade()

            except RuntimeError:
                self.logger.debug(
                    'Existing credential use failed',
                    exc_info=True,
                )
                msg = _(
                    'Cannot connect to ovirt cinderlib '
                    'database using existing '
                    'credentials: {user}@{host}:{port}'
                ).format(
                    host=dbenv[oclcons.CinderlibDBEnv.HOST],
                    port=dbenv[oclcons.CinderlibDBEnv.PORT],
                    database=dbenv[oclcons.CinderlibDBEnv.DATABASE],
                    user=dbenv[oclcons.CinderlibDBEnv.USER],
                )
                if self.environment[
                    osetupcons.CoreEnv.ACTION
                ] == osetupcons.Const.ACTION_REMOVE:
                    self.logger.warning(msg)
                else:
                    raise RuntimeError(msg)
            if not self.environment[
                oclcons.CinderlibDBEnv.NEW_DATABASE
            ]:
                statement = database.Statement(
                    dbenvkeys=oclcons.Const.CINDERLIB_DB_ENV_KEYS,
                    environment=self.environment,
                )
                try:
                    justRestored = vdcoption.VdcOption(
                        statement=statement,
                    ).getVdcOption(
                        'DbJustRestored',
                        ownConnection=True,
                    )
                    self.environment[
                        oclcons.CinderlibDBEnv.JUST_RESTORED
                    ] = (justRestored == '1')
                except RuntimeError:
                    pass
                if self.environment[
                    oclcons.CinderlibDBEnv.JUST_RESTORED
                ]:
                    self.logger.info(_(
                        'The ovirt cinderlib DB has been'
                        ' restored from a backup'
                    ))


# vim: expandtab tabstop=4 shiftwidth=4