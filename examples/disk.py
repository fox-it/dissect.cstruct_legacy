import sys
from dissect import cstruct

disk_def = """
#define MAX_MBR_CODE_SIZE 0x1b6
#define MBR_SIZE 0x200
#define PART_DOS_EXTD 5
#define PART_WIN_EXTD_LBA 0xF
#define PART_LINUX_EXTD 0x85

typedef struct sig_s {
    char        str[13];
} sig;

typedef struct part_s {
    uint8       bootable;               // +0: 0x80/0x00 - bootable/not bootable
    uint8   start_head;         // +1: head (start)
    uint16  start_cyl_sec;  // +2: cyl+sect (start)
    uint8   type;               // +4: type
    uint8   end_head;           // +5: head (end)
    uint16  end_cyl_sec;    // +6: cyl+sec (end)
    uint32  sector_ofs;         // +8: offset in sectors
    uint32  sector_size;    // +12: size in sectors
} part;

typedef struct mbr_s {
    uint8       jmp[3];
    sig     signature;
    uint8   crlf[3];            /* 10 */
    uint8   default_char;   /* 13 */
    uint8   chars[4];           /* 14 */
    uint16  delay;              /* 18 */
    uint16  offsets[4];         /* 1a..20 */
    char    rest_of_code[0x1b6-0x22];
    uint16  pad1;
    uint32  vol_no;
    uint16  pad2;
    part    part[4];
    uint16  bootsig;
} mbr;

// http://en.wikipedia.org/wiki/GUID_Partition_Table
struct GPT_HEADER {
    char        signature[8];
    uint32      revision;
    uint32      header_size;
    uint32      crc32;
    uint32      reserved;
    uint64      current_lba;
    uint64      backup_lba;
    uint64      first_usable_lba;
    uint64      last_usable_lba;
    uint8       guid[16];
    uint64      lba_partition_array;
    uint32      partition_table_count;
    uint32      partition_entry_size;
    uint32      partition_table_crc;
    char        _[420];
};

struct GPT_PARTITION {
    uint8       type_guid[16];
    char        partition_guid[16];
    uint64      first_lba;
    uint64      last_lba;
    uint64      attribute_flags;
    wchar       name[36];
};

// 0 (0x00)        16 bytes        Partition type GUID
// 16 (0x10)   16 bytes    Unique partition GUID
// 32 (0x20)   8 bytes     First LBA (little endian)
// 40 (0x28)   8 bytes     Last LBA (inclusive, usually odd)
// 48 (0x30)   8 bytes     Attribute flags (e.g. bit 60 denotes read-only)
// 56 (0x38)   72 bytes    Partition name (36 UTF-16LE code units)
"""

c_disk = cstruct.cstruct()
c_disk.load(disk_def)

SECTOR_SIZE = 512


class Partition(object):
    def __init__(self, disk, offset, size, vtype, name, guid=None):
        self.disk = disk
        self.offset = offset
        self.size = size
        self.type = vtype
        self.name = name
        self.guid = guid

    def __repr__(self):
        return "<Partition offset=0x{:x} size=0x{:x} type={} name={}>".format(self.offset, self.size, self.type, self.name)


def partitions(fh, mbr, offset):
    for p in mbr.part:
        part_offset = offset + p.sector_ofs * SECTOR_SIZE

        if p.type == 0x00:
            continue

        if p.type == 0x05:
            fh.seek(part_offset)
            e_mbr = c_disk.mbr(fh)
            for part in partitions(fh, e_mbr, part_offset):
                yield part

        yield Partition(fh, part_offset, p.sector_size * SECTOR_SIZE, p.type, None)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("usage: disk.py <disk or image>")

    fh = open(sys.argv[1], 'rb')
    mbr = c_disk.mbr(fh)

    if mbr.bootsig != 0xaa55:
        sys.exit("Not a valid MBR")

    cstruct.dumpstruct(mbr)

    for p in partitions(fh, mbr, 0):
        if p.type == 0xee:
            fh.seek(p.offset)
            gpt = c_disk.GPT_HEADER(fh)
            cstruct.dumpstruct(gpt)

            fh.seek(gpt.lba_partition_array * SECTOR_SIZE)
            for _ in range(gpt.partition_table_count):
                p = c_disk.GPT_PARTITION(fh)
                if p.first_lba == 0:
                    break

                part = Partition(
                    fh, p.first_lba * SECTOR_SIZE, (p.last_lba - p.first_lba) * SECTOR_SIZE,
                    p.type_guid, p.name.rstrip('\x00'), guid=p.partition_guid
                )
                print(part)

            continue

        print(p)
