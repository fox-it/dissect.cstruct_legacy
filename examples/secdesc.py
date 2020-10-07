#!/usr/bin/env python
# flake8: noqa
import zlib
import binascii
from io import BytesIO

from dissect.cstruct import cstruct

cdef = """
struct SECURITY_DESCRIPTOR {
    uint8   Revision;
    uint8   Sbz1;
    uint16  Control;
    uint32  OffsetOwner;
    uint32  OffsetGroup;
    uint32  OffsetSacl;
    uint32  OffsetDacl;
};

struct LDAP_SID_IDENTIFIER_AUTHORITY {
    char    Value[6];
};

struct LDAP_SID {
    uint8   Revision;
    uint8   SubAuthorityCount;
    LDAP_SID_IDENTIFIER_AUTHORITY   IdentifierAuthority;
    uint32  SubAuthority[SubAuthorityCount];
};

struct ACL {
    uint8   AclRevision;
    uint8   Sbz1;
    uint16  AclSize;
    uint16  AceCount;
    uint16  Sbz2;
    char    Data[AclSize - 8];
};

struct ACE {
    uint8   AceType;
    uint8   AceFlags;
    uint16  AceSize;
    char    Data[AceSize - 4];
};

struct ACCESS_ALLOWED_ACE {
    uint16  Mask;
    LDAP_SID Sid;
};

struct ACCESS_ALLOWED_OBJECT_ACE {
    uint32  Mask;
    uint32  Flags;
    char    ObjectType[Flags & 1 * 16];
    char    InheritedObjectType[Flags & 2 * 8];
    LDAP_SID Sid;
};
"""
c_secd = cstruct()
c_secd.load(cdef, compiled=True)


class SecurityDescriptor(object):
    def __init__(self, fh):
        self.fh = fh
        self.descriptor = c_secd.SECURITY_DESCRIPTOR(fh)

        self.owner_sid = b''
        self.group_sid = b''
        self.sacl = b''
        self.dacl = b''

        if self.descriptor.OffsetOwner != 0:
            fh.seek(self.descriptor.OffsetOwner)
            self.owner_sid = LdapSid(fh=fh)

        if self.descriptor.OffsetGroup != 0:
            fh.seek(self.descriptor.OffsetGroup)
            self.group_sid = LdapSid(fh=fh)

        if self.descriptor.OffsetSacl != 0:
            fh.seek(self.descriptor.OffsetSacl)
            self.sacl = ACL(fh)

        if self.descriptor.OffsetDacl != 0:
            fh.seek(self.descriptor.OffsetDacl)
            self.dacl = ACL(fh)


class LdapSid(object):
    def __init__(self, fh=None, in_obj=None):
        if fh:
            self.fh = fh
            self.ldap_sid = c_secd.LDAP_SID(fh)
        else:
            self.ldap_sid = in_obj

    def __repr__(self):
        return "S-{}-{}-{}".format(
            self.ldap_sid.Revision,
            bytearray(self.ldap_sid.IdentifierAuthority.Value)[5],
            "-".join(['{:d}'.format(v) for v in self.ldap_sid.SubAuthority])
        )


class ACL(object):
    def __init__(self, fh):
        self.fh = fh
        self.acl = c_secd.ACL(fh)
        self.aces = []

        buf = BytesIO(self.acl.Data)
        for i in range(self.acl.AceCount):
            self.aces.append(ACE(buf))


class ACCESS_ALLOWED_ACE(object):
    def __init__(self, fh):
        self.fh = fh
        self.data = c_secd.ACCESS_ALLOWED_ACE(fh)
        self.sid = LdapSid(in_obj=self.data.Sid)


class ACCESS_DENIED_ACE(ACCESS_ALLOWED_ACE):
    pass


class ACCESS_ALLOWED_OBJECT_ACE(object):
    # Flag constants
    ACE_OBJECT_TYPE_PRESENT = 0x01
    ACE_INHERITED_OBJECT_TYPE_PRESENT = 0x02

    # ACE type specific mask constants
    # Note that while not documented, these also seem valid
    # for ACCESS_ALLOWED_ACE types
    ADS_RIGHT_DS_CONTROL_ACCESS = 0x00000100
    ADS_RIGHT_DS_CREATE_CHILD = 0x00000001
    ADS_RIGHT_DS_DELETE_CHILD = 0x00000002
    ADS_RIGHT_DS_READ_PROP = 0x00000010
    ADS_RIGHT_DS_WRITE_PROP = 0x00000020
    ADS_RIGHT_DS_SELF = 0x00000008

    def __init__(self, fh):
        self.fh = fh
        self.data = c_secd.ACCESS_ALLOWED_OBJECT_ACE(fh)
        self.sid = LdapSid(in_obj=self.data.Sid)


class ACCESS_DENIED_OBJECT_ACE(ACCESS_ALLOWED_OBJECT_ACE):
    pass


class ACCESS_MASK(object):
    """
    ACCESS_MASK as described in 2.4.3
    https://msdn.microsoft.com/en-us/library/cc230294.aspx
    """
    # Flag constants
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x04000000
    GENERIC_EXECUTE = 0x20000000
    GENERIC_ALL = 0x10000000
    MAXIMUM_ALLOWED = 0x02000000
    ACCESS_SYSTEM_SECURITY = 0x01000000
    SYNCHRONIZE = 0x00100000
    WRITE_OWNER = 0x00080000
    WRITE_DACL = 0x00040000
    READ_CONTROL = 0x00020000
    DELETE = 0x00010000

    def __init__(self, mask):
        self.mask = mask

    def has_priv(self, priv):
        return (self.mask & priv) == priv

    def set_priv(self, priv):
        self.mask |= priv

    def remove_priv(self, priv):
        self.mask ^= priv


class ACE(object):
    CONTAINER_INHERIT_ACE = 0x01
    FAILED_ACCESS_ACE_FLAG = 0x80
    INHERIT_ONLY_ACE = 0x08
    INHERITED_ACE = 0x10
    NO_PROPAGATE_INHERIT_ACE = 0x04
    OBJECT_INHERIT_ACE = 0x01
    SUCCESSFUL_ACCESS_ACE_FLAG = 0x04

    def __init__(self, fh):
        self.fh = fh
        self.ace = c_secd.ACE(fh)
        self.acedata = None
        buf = BytesIO(self.ace.Data)
        if self.ace.AceType == 0x00:
            # ACCESS_ALLOWED_ACE
            self.acedata = ACCESS_ALLOWED_ACE(buf)
        elif self.ace.AceType == 0x05:
            # ACCESS_ALLOWED_OBJECT_ACE
            self.acedata = ACCESS_ALLOWED_OBJECT_ACE(buf)
        elif self.ace.AceType == 0x01:
            # ACCESS_DENIED_ACE
            self.acedata = ACCESS_DENIED_ACE(buf)
        elif self.ace.AceType == 0x06:
            # ACCESS_DENIED_OBJECT_ACE
            self.acedata = ACCESS_DENIED_OBJECT_ACE(buf)
        # else:
        #     print 'Unsupported type %d' % self.ace.AceType

        if self.acedata:
            self.mask = ACCESS_MASK(self.acedata.data.Mask)

    def __repr__(self):
        return repr(self.ace)


if __name__ == '__main__':
    d = BytesIO(zlib.decompress(binascii.unhexlify(
        '789c636410e949916060680062110606861e206661a8606002d2ec51160c0a409a1988f759f37dfe30'
        'ffa2e03620e70773fac1a555d3f63fe3bd20b8a89561158381e723464606100093c8faf693a08f85e1'
        '867809906665f080eb175050885f5a7941708202c301ff4357ceb7a1eb6705eb671505d9354365a9b7'
        'e91ff127ae3ed9200f209b135089aa8f5c7382a964ce85fd5c7659421704172400f5e518bf25cd1c0b'
        '060e68a0b94f7d5c24517d5170ed7b60f8dcb87a96587d1deecb3eb3055f145c7914122f84f429c022'
        'c949cce780c205c1e5194077e6b16a12d26700d5574fa4ff58c1fa74c06104d2b7025d1f13441fc83d'
        '6a50b50250b5b21b57baad4b8872d8fee27f57c495b04bc86a0dc06a35c00a416a83a58a56ebcb5d10'
        '9c210934d7216836723a04a9c319be1075ac5c68ea30c2134d1d2c1cda766c2df79a725170dd5e4c75'
        '0c0c2a0c57189919f0852948cd7f467e026a24206a90fcaf02668b40c215c54e118629404d30316ea8'
        '18583f544c084c20f2b42987ce8e17323ece3b3e843c929ab7e12646da45f6bb10240d80f4bd09489a'
        'bffbbeae7383e263e5eb9f184ee0d527e5010e30662c71b58bc8b454c6826a4ec1544d865c1544da25'
        'd51c76a83f184f969e7c9593efdd2c79added5652a1bb1e694b040c283119a1644ce6878988bec719d'
        'cdbe369f312e5e03affd48fa882d2bd0f5cd21531f46994da43e92c21749df05b92d313e7c407d6dc4'
        'e983e57f62cba642347de24b366f0c7d33d171b3fa763de3c75d9f08c51f4c9febcdaa59c1a72e0aee'
        'bec0d0703cade000b1fa32484c2f307d9d5d9af233eeed70df7a365cebaaad5a1db1fa26569267df42'
        '952bf149487514217d0a507d6c44fa2f834c7da568fab8484c67307d7cdf4aec8aed8065f601fc7520'
        'ba3b89d587ee4e62d319ba7dc4ea43b74f8ac87847b78f587de8f6c931cd9a15ed050c97c3f8c3053d'
        'bd281c9cc674cb817078a2c79fda4bdfc9f3365c125cc506ac9bfbdede20d63e770bd3b89ccffb3c96'
        '7ff7cc08610ab021565fc029ebde3a59607e68242d3fa0b719898d0762f5a1c7430863ef931f7b2e0a'
        'b63301c365674200d1faf4a3d575679cf5ddb0f6a929a34bdc6f62fd1742a6ff88d587eece4432ed23'
        '561fba7dc496d7e8e9b390c8f2135d5ff97383905787551c26e8dd7d3849c12d93d878a84c48c86fb2'
        '92f6e9fb7de7c44959b57fc4eaab22d37fc4b6e9d1ed6b7ae595786cf505df851ed7aa228f6b8811ab'
        'afa5d239ede8e17ecf4d99332a24df7b7813ab0fa3cd4d64bc7796dc5ff1ea28b07e3f8dbf7e474f67'
        'c4eac3b08fc8fa1dc33e22f5a1db37ebff8f0f130509a74f74fb88d5871e0fc4ea4377e7dcbc033a75'
        'f9594e1daa4ca2f7c4f30489b58fd8f60bbaff88d587eece1d8f938db2ff26f8b47f32d9bb6a6ee66b'
        '62ddb9872f59e3aa23b0fe3b485a3b84587de8ee3c406439889edfd1c72c88d577f9f8969af6f60d4e'
        '5b2c6c62dd675d9623142eb0be32ff35f7e809099b1ce69b6bf9bee83748c6a58f0fd4b797b2607060'
        '6001777f49ea5721e923b5bf02ee2303e53678763036aebc24b8f23ffe76480699fa4aa1ee04850ac9'
        'fe1342e823a9df88641f49fd46247d24f51b91f491d62f47e823a9df2880180b5b96cb34db8637c6ad'
        'fb5de0cceb6231bbf08e694941f43163d187633c83196c9810c9fae0e32702507db9f38e6d3fae7349'
        'b0d58f61c1c9e66f1cb8f4713240dc894b1f467c12a90f235e90f5218d0f4dae967ee51177d56d4f8e'
        'ef97bfcbbb4cf18ff3e880c79fb0a66ba4f12b2d2654b5187ec0a316c3dde86a8534708f0540dd2ac2'
        '80aa0ea3ce85aae386aa8395614f0f57d8cffabed76dc18eb91282b9772a51e316a88e11a2ee9efbb3'
        '89f9370bbca7865fb3fff2f9cc0d94313a2115c8181d9e7285909a52a81a7c6387ec4c84d5f083d548'
        '30808c430f4790f85eb4714705201b5f7ec2270700bed3f0c5')))

    sc = SecurityDescriptor(d)

    # print sc.descriptor
    # print sc.owner_sid
    # print sc.group_sid
    # print sc.sacl.acl
    # print sc.sacl.aces
    # print sc.dacl.acl
    # print sc.dacl.aces

    for i in sc.dacl.aces:
        if i.ace.AceType == 0x05:
            print(i.acedata.sid)
