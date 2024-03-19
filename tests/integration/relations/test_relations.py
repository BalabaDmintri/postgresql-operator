#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import asyncio
import logging
import secrets
import string
from pathlib import Path
from time import sleep

import psycopg2
import pytest
import yaml
from pytest_operator.plugin import OpsTest, FileResource
from tenacity import Retrying, stop_after_delay, wait_fixed

from tests.integration.helpers import CHARM_SERIES, DATABASE_APP_NAME, METADATA, get_unit_address, get_password
from tests.integration.relations.helpers import get_legacy_db_connection_str
from tests.integration.relations.new_relations.helpers import build_connection_string
from tests.integration.relations.new_relations.test_new_relations import APPLICATION_APP_NAME

logger = logging.getLogger(__name__)

APP_NAME = METADATA["name"]
MAILMAN3_CORE_APP_NAME = "mailman3-core"
DB_RELATION = "db"
DATABASE_RELATION = "database"
FIRST_DATABASE_RELATION = "first-database"
APP_NAMES = [APP_NAME, APPLICATION_APP_NAME, MAILMAN3_CORE_APP_NAME]


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_deploy_charms(ops_test: OpsTest, charm):
    """Deploy both charms (application and database) to use in the tests."""
    # Deploy both charms (multiple units for each application to test that later they correctly
    # set data in the relation application databag using only the leader unit).
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.deploy(
                APPLICATION_APP_NAME,
                application_name=APPLICATION_APP_NAME,
                num_units=1,
                series=CHARM_SERIES,
                channel="edge",
            ),
            ops_test.model.deploy(
                charm,
                application_name=DATABASE_APP_NAME,
                num_units=1,
                series=CHARM_SERIES,
                config={"profile": "testing"},
            ),
            ops_test.model.deploy(
                MAILMAN3_CORE_APP_NAME,
                application_name=MAILMAN3_CORE_APP_NAME,
                channel="stable",
                config={"hostname": "example.org"},
            ),
        )

        await ops_test.model.wait_for_idle(apps=APP_NAMES, status="active", timeout=3000)


@pytest.mark.group(1)
async def test_legacy_modern_endpoints(ops_test: OpsTest):
    await ops_test.model.relate(MAILMAN3_CORE_APP_NAME, f"{APP_NAME}:{DB_RELATION}")
    await ops_test.model.relate(APP_NAME, f"{APPLICATION_APP_NAME}:{FIRST_DATABASE_RELATION}")

    app = ops_test.model.applications[APP_NAME]
    logger.info(f"  ========  app  {app.name}")
    await ops_test.model.block_until(
        lambda: "blocked" in {unit.workload_status for unit in app.units},
        timeout=1500,
    )

    logger.info(f"  ========  remove-relation")
    await ops_test.model.applications[APP_NAME].remove_relation(
             f"{APP_NAME}:{DATABASE_RELATION}", f"{APPLICATION_APP_NAME}:{FIRST_DATABASE_RELATION}"
    )
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
    sleep(60*5)
    # host = get_unit_address(ops_test, f"{APP_NAME}/0")
    # password = await get_password(ops_test, f"{APP_NAME}/0")
    # # modern_interface_connect = (f"dbname='{APPLICATION_NAME.replace('-', '_')}_first_database' user='operator' "
    # #                             f"host='{host}'"
    # #                             f" password='{password}' connect_timeout=10")
    # modern_interface_connect = await build_connection_string(ops_test, APPLICATION_APP_NAME, FIRST_DATABASE_RELATION)
    #
    # for attempt in Retrying(stop=stop_after_delay(60 * 3), wait=wait_fixed(10)):
    #     with attempt:
    #         with psycopg2.connect(modern_interface_connect) as connection:
    #             assert connection.status == psycopg2.extensions.STATUS_READY
    #
    # database_unit_name = ops_test.model.applications[APP_NAME].units[0].name
    # logger.info(f"  ====================  database_unit_name  ={database_unit_name}")
    # legacy_interface_connect = await get_legacy_db_connection_str(ops_test, MAILMAN3_CORE_APP_NAME, DB_RELATION,
    #                                                               remote_unit_name=f"{APP_NAME}/0")
    # logger.info(f"============  legacy_interface_connect= {legacy_interface_connect}")
    # for attempt in Retrying(stop=stop_after_delay(60 * 3), wait=wait_fixed(10)):
    #     with attempt:
    #         with psycopg2.connect(legacy_interface_connect) as connection:
    #             assert connection.status == psycopg2.extensions.STATUS_READY
    #
    # logger.info(f"==== remove relation mailman3-core")
    # async with ops_test.fast_forward():
    #     await ops_test.model.applications[APP_NAME].remove_relation(
    #         f"{APP_NAME}:db", f"mailman3-core:db"
    #     )
    #     await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
    #     with pytest.raises(psycopg2.OperationalError):
    #         psycopg2.connect(legacy_interface_connect)
    #
    # logger.info(f"==== remove relation {APPLICATION_APP_NAME}")
    # async with ops_test.fast_forward():
    #     await ops_test.model.applications[APP_NAME].remove_relation(
    #         f"{APP_NAME}:{DATABASE_RELATION}", f"{APPLICATION_APP_NAME}:{FIRST_DATABASE_RELATION}"
    #     )
    #     await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
    #     for attempt in Retrying(stop=stop_after_delay(60 * 5), wait=wait_fixed(10)):
    #         with attempt:
    #             with pytest.raises(psycopg2.OperationalError):
    #                 connection = psycopg2.connect(modern_interface_connect)
    #                 logger.info(f"============  status  = {connection.status}")
    #                 # assert connection.status == psycopg2.extensions.STATUS_READY
