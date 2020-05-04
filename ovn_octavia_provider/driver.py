#    Copyright 2020 Red Hat, Inc. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import re

import netaddr
from octavia_lib.api.drivers import data_models as o_datamodels
from octavia_lib.api.drivers import exceptions as driver_exceptions
from octavia_lib.api.drivers import provider_base as driver_base
from octavia_lib.common import constants
from oslo_log import log as logging

from ovn_octavia_provider.common import config as ovn_conf
# TODO(mjozefcz): Start consuming const and utils
# from neutron-lib once released.
from ovn_octavia_provider.common import constants as ovn_const
from ovn_octavia_provider.common import exceptions as ovn_exc
from ovn_octavia_provider import helper as ovn_helper
from ovn_octavia_provider.i18n import _

ovn_conf.register_opts()

LOG = logging.getLogger(__name__)


class OvnProviderDriver(driver_base.ProviderDriver):

    def __init__(self):
        super(OvnProviderDriver, self).__init__()
        self._ovn_helper = ovn_helper.OvnProviderHelper()

    def __del__(self):
        self._ovn_helper.shutdown()

    def _check_for_supported_protocols(self, protocol):
        if protocol not in ovn_const.OVN_NATIVE_LB_PROTOCOLS:
            msg = _('OVN provider does not support %s protocol') % protocol
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)

    def _check_for_supported_algorithms(self, algorithm):
        if algorithm not in ovn_const.OVN_NATIVE_LB_ALGORITHMS:
            msg = _('OVN provider does not support %s algorithm') % algorithm
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)

    def loadbalancer_create(self, loadbalancer):
        admin_state_up = loadbalancer.admin_state_up
        if isinstance(admin_state_up, o_datamodels.UnsetType):
            admin_state_up = True
        request_info = {'id': loadbalancer.loadbalancer_id,
                        'vip_address': loadbalancer.vip_address,
                        'vip_network_id': loadbalancer.vip_network_id,
                        'admin_state_up': admin_state_up}

        request = {'type': ovn_const.REQ_TYPE_LB_CREATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def loadbalancer_delete(self, loadbalancer, cascade=False):
        request_info = {'id': loadbalancer.loadbalancer_id,
                        'cascade': cascade}
        request = {'type': ovn_const.REQ_TYPE_LB_DELETE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def loadbalancer_failover(self, loadbalancer_id):
        request_info = {'id': loadbalancer_id}
        request = {'type': ovn_const.REQ_TYPE_LB_FAILOVER,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def loadbalancer_update(self, old_loadbalancer, new_loadbalancer):
        request_info = {'id': new_loadbalancer.loadbalancer_id}
        if not isinstance(
                new_loadbalancer.admin_state_up, o_datamodels.UnsetType):
            request_info['admin_state_up'] = new_loadbalancer.admin_state_up
        request = {'type': ovn_const.REQ_TYPE_LB_UPDATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    # Pool
    def pool_create(self, pool):
        self._check_for_supported_protocols(pool.protocol)
        self._check_for_supported_algorithms(pool.lb_algorithm)
        admin_state_up = pool.admin_state_up
        if isinstance(admin_state_up, o_datamodels.UnsetType):
            admin_state_up = True
        request_info = {'id': pool.pool_id,
                        'loadbalancer_id': pool.loadbalancer_id,
                        'protocol': pool.protocol,
                        'listener_id': pool.listener_id,
                        'admin_state_up': admin_state_up}
        request = {'type': ovn_const.REQ_TYPE_POOL_CREATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def pool_delete(self, pool):
        for member in pool.members:
            self.member_delete(member)

        request_info = {'id': pool.pool_id,
                        'protocol': pool.protocol,
                        'loadbalancer_id': pool.loadbalancer_id}
        request = {'type': ovn_const.REQ_TYPE_POOL_DELETE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def pool_update(self, old_pool, new_pool):
        if not isinstance(new_pool.protocol, o_datamodels.UnsetType):
            self._check_for_supported_protocols(new_pool.protocol)
        if not isinstance(new_pool.lb_algorithm, o_datamodels.UnsetType):
            self._check_for_supported_algorithms(new_pool.lb_algorithm)
        request_info = {'id': old_pool.pool_id,
                        'protocol': old_pool.protocol,
                        'loadbalancer_id': old_pool.loadbalancer_id}

        if not isinstance(new_pool.admin_state_up, o_datamodels.UnsetType):
            request_info['admin_state_up'] = new_pool.admin_state_up
        request = {'type': ovn_const.REQ_TYPE_POOL_UPDATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def listener_create(self, listener):
        self._check_for_supported_protocols(listener.protocol)
        admin_state_up = listener.admin_state_up
        if isinstance(admin_state_up, o_datamodels.UnsetType):
            admin_state_up = True
        request_info = {'id': listener.listener_id,
                        'protocol': listener.protocol,
                        'loadbalancer_id': listener.loadbalancer_id,
                        'protocol_port': listener.protocol_port,
                        'default_pool_id': listener.default_pool_id,
                        'admin_state_up': admin_state_up}
        request = {'type': ovn_const.REQ_TYPE_LISTENER_CREATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def listener_delete(self, listener):
        request_info = {'id': listener.listener_id,
                        'loadbalancer_id': listener.loadbalancer_id,
                        'protocol_port': listener.protocol_port,
                        'protocol': listener.protocol}
        request = {'type': ovn_const.REQ_TYPE_LISTENER_DELETE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def listener_update(self, old_listener, new_listener):
        request_info = {'id': new_listener.listener_id,
                        'loadbalancer_id': old_listener.loadbalancer_id,
                        'protocol': old_listener.protocol,
                        'protocol_port': old_listener.protocol_port}

        if not isinstance(new_listener.admin_state_up, o_datamodels.UnsetType):
            request_info['admin_state_up'] = new_listener.admin_state_up

        if not isinstance(new_listener.default_pool_id,
                          o_datamodels.UnsetType):
            request_info['default_pool_id'] = new_listener.default_pool_id

        request = {'type': ovn_const.REQ_TYPE_LISTENER_UPDATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    # Member
    def _check_monitor_options(self, member):
        if (isinstance(member.monitor_address, o_datamodels.UnsetType) and
                isinstance(member.monitor_port, o_datamodels.UnsetType)):
            return False
        if member.monitor_address or member.monitor_port:
            return True
        return False

    def _ip_version_differs(self, member):
        _, ovn_lb = self._ovn_helper._find_ovn_lb_by_pool_id(member.pool_id)
        lb_vip = ovn_lb.external_ids[ovn_const.LB_EXT_IDS_VIP_KEY]
        return netaddr.IPNetwork(lb_vip).version != (
            netaddr.IPNetwork(member.address).version)

    def member_create(self, member):
        if self._check_monitor_options(member):
            msg = _('OVN provider does not support monitor options')
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)
        if self._ip_version_differs(member):
            raise ovn_exc.IPVersionsMixingNotSupportedError()
        admin_state_up = member.admin_state_up
        if (isinstance(member.subnet_id, o_datamodels.UnsetType) or
                not member.subnet_id):
            msg = _('Subnet is required for Member creation '
                    'with OVN Provider Driver')
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)

        if isinstance(admin_state_up, o_datamodels.UnsetType):
            admin_state_up = True
        request_info = {'id': member.member_id,
                        'address': member.address,
                        'protocol_port': member.protocol_port,
                        'pool_id': member.pool_id,
                        'subnet_id': member.subnet_id,
                        'admin_state_up': admin_state_up}
        request = {'type': ovn_const.REQ_TYPE_MEMBER_CREATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

        # NOTE(mjozefcz): If LB has FIP on VIP
        # and member has FIP we need to centralize
        # traffic for member.
        request_info = {'id': member.member_id,
                        'address': member.address,
                        'pool_id': member.pool_id,
                        'subnet_id': member.subnet_id,
                        'action': ovn_const.REQ_INFO_MEMBER_ADDED}
        request = {'type': ovn_const.REQ_TYPE_HANDLE_MEMBER_DVR,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def member_delete(self, member):
        request_info = {'id': member.member_id,
                        'address': member.address,
                        'protocol_port': member.protocol_port,
                        'pool_id': member.pool_id,
                        'subnet_id': member.subnet_id}
        request = {'type': ovn_const.REQ_TYPE_MEMBER_DELETE,
                   'info': request_info}
        self._ovn_helper.add_request(request)
        # NOTE(mjozefcz): If LB has FIP on VIP
        # and member had FIP we can decentralize
        # the traffic now.
        request_info = {'id': member.member_id,
                        'address': member.address,
                        'pool_id': member.pool_id,
                        'subnet_id': member.subnet_id,
                        'action': ovn_const.REQ_INFO_MEMBER_DELETED}
        request = {'type': ovn_const.REQ_TYPE_HANDLE_MEMBER_DVR,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def member_update(self, old_member, new_member):
        if self._check_monitor_options(new_member):
            msg = _('OVN provider does not support monitor options')
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)
        if new_member.address and self._ip_version_differs(new_member):
            raise ovn_exc.IPVersionsMixingNotSupportedError()
        request_info = {'id': new_member.member_id,
                        'address': old_member.address,
                        'protocol_port': old_member.protocol_port,
                        'pool_id': old_member.pool_id,
                        'subnet_id': old_member.subnet_id}
        if not isinstance(new_member.admin_state_up, o_datamodels.UnsetType):
            request_info['admin_state_up'] = new_member.admin_state_up
        request = {'type': ovn_const.REQ_TYPE_MEMBER_UPDATE,
                   'info': request_info}
        self._ovn_helper.add_request(request)

    def member_batch_update(self, members):
        # Note(rbanerje): all members belong to the same pool.
        request_list = []
        skipped_members = []
        pool_id = None
        try:
            pool_id = members[0].pool_id
        except IndexError:
            msg = _('No member information has been passed')
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)
        except AttributeError:
            msg = _('Member does not have proper pool information')
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)
        pool_key, ovn_lb = self._ovn_helper._find_ovn_lb_by_pool_id(pool_id)
        external_ids = copy.deepcopy(ovn_lb.external_ids)
        existing_members = external_ids[pool_key].split(',')
        members_to_delete = copy.copy(existing_members)
        for member in members:
            if (self._check_monitor_options(member) or
                    member.address and self._ip_version_differs(member)):
                skipped_members.append(member.member_id)
                continue
            # NOTE(mjozefcz): We need to have subnet_id information.
            if (isinstance(member.subnet_id, o_datamodels.UnsetType) or
                    not member.subnet_id):
                msg = _('Subnet is required for Member creation '
                        'with OVN Provider Driver')
                raise driver_exceptions.UnsupportedOptionError(
                    user_fault_string=msg,
                    operator_fault_string=msg)
            admin_state_up = member.admin_state_up
            if isinstance(admin_state_up, o_datamodels.UnsetType):
                admin_state_up = True

            member_info = self._ovn_helper._get_member_key(member)
            # TODO(mjozefcz): Remove this workaround in W release.
            member_info_old = self._ovn_helper._get_member_key(
                member, old_convention=True)
            member_found = [x for x in existing_members
                            if re.match(member_info_old, x)]
            if not member_found:
                req_type = ovn_const.REQ_TYPE_MEMBER_CREATE
            else:
                # If member exists in pool, then Update
                req_type = ovn_const.REQ_TYPE_MEMBER_UPDATE
                # Remove all updating members so only deleted ones are left
                # TODO(mjozefcz): Remove this workaround in W release.
                try:
                    members_to_delete.remove(member_info_old)
                except ValueError:
                    members_to_delete.remove(member_info)

            request_info = {'id': member.member_id,
                            'address': member.address,
                            'protocol_port': member.protocol_port,
                            'pool_id': member.pool_id,
                            'subnet_id': member.subnet_id,
                            'admin_state_up': admin_state_up}
            request = {'type': req_type,
                       'info': request_info}
            request_list.append(request)

        for member in members_to_delete:
            member_info = member.split('_')
            request_info = {'id': member_info[1],
                            'address': member_info[2].split(':')[0],
                            'protocol_port': member_info[2].split(':')[1],
                            'pool_id': pool_id}
            if len(member_info) == 4:
                request_info['subnet_id'] = member_info[3]
            request = {'type': ovn_const.REQ_TYPE_MEMBER_DELETE,
                       'info': request_info}
            request_list.append(request)

        for request in request_list:
            self._ovn_helper.add_request(request)
        if skipped_members:
            msg = (_('OVN provider does not support monitor options, '
                     'so following members skipped: %s') % skipped_members)
            raise driver_exceptions.UnsupportedOptionError(
                user_fault_string=msg,
                operator_fault_string=msg)

    def create_vip_port(self, lb_id, project_id, vip_dict):
        try:
            port = self._ovn_helper.create_vip_port(
                project_id, lb_id, vip_dict)['port']
            vip_dict[constants.VIP_PORT_ID] = port['id']
            vip_dict[constants.VIP_ADDRESS] = (
                port['fixed_ips'][0]['ip_address'])
        except Exception as e:
            raise driver_exceptions.DriverError(e)
        return vip_dict
