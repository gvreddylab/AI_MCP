import oci
import csv

# Path to save the report
REPORT_FILE = "oci_inventory_report.csv"

# Load OCI config
config = oci.config.from_file()

# Create clients
identity_client = oci.identity.IdentityClient(config)
virtual_network_client = oci.core.VirtualNetworkClient(config)
compute_client = oci.core.ComputeClient(config)
blockstorage_client = oci.core.BlockstorageClient(config)

def get_all_compartments(identity_client, tenancy_id):
    compartments = []
    list_compartments_response = identity_client.list_compartments(
        tenancy_id,
        compartment_id_in_subtree=True,
        access_level="ANY"
    )
    compartments.extend(list_compartments_response.data)
    return compartments

def get_vcns(virtual_network_client, compartment_id):
    vcns = virtual_network_client.list_vcns(compartment_id).data
    return vcns

def get_subnets(virtual_network_client, compartment_id):
    subnets = virtual_network_client.list_subnets(compartment_id).data
    return subnets

def get_instances(compute_client, compartment_id):
    instances = compute_client.list_instances(compartment_id).data
    return instances

def get_shape_details(compute_client, shape, compartment_id):
    try:
        shape_details = compute_client.get_shape(compartment_id, shape).data
        return shape_details
    except Exception:
        return None

def get_image_name(compute_client, image_id):
    try:
        image = compute_client.get_image(image_id).data
        return image.display_name
    except Exception:
        return "Unknown"

def get_boot_volume_size(blockstorage_client, boot_volume_id):
    try:
        boot_volume = blockstorage_client.get_boot_volume(boot_volume_id).data
        return boot_volume.size_in_gbs
    except Exception:
        return "Unknown"

def main():
    tenancy_id = config["tenancy"]
    compartments = get_all_compartments(identity_client, tenancy_id)
    # Build compartment, VCN, subnet maps for lookup
    compartment_map = {c.id: c for c in compartments}
    vcn_map = {}
    subnet_map = {}
    for compartment in compartments:
        for vcn in get_vcns(virtual_network_client, compartment.id):
            vcn_map[vcn.id] = (vcn.display_name, vcn.compartment_id)
        for subnet in get_subnets(virtual_network_client, compartment.id):
            subnet_map[subnet.id] = (subnet.display_name, subnet.vcn_id, subnet.compartment_id)

    with open(REPORT_FILE, "w", encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Compartment Name", "Compartment OCID", "VCN Name", "VCN OCID", "Subnet Name", "Subnet OCID",
            "Instance Name", "Instance OCID", "CPU (OCPUs)", "Memory (GB)", "Boot Volume (GB)", "Image Name"
        ])
        for compartment in compartments:
            instances = get_instances(compute_client, compartment.id)
            for instance in instances:
                # Get subnet info
                subnet_id = instance.subnet_id if hasattr(instance, 'subnet_id') else None
                subnet_name, vcn_id, subnet_compartment_id = ("", "", "")
                vcn_name = ""
                if subnet_id and subnet_id in subnet_map:
                    subnet_name, vcn_id, subnet_compartment_id = subnet_map[subnet_id]
                    vcn_name = vcn_map[vcn_id][0] if vcn_id in vcn_map else ""
                # Get shape details
                shape_details = get_shape_details(compute_client, instance.shape, compartment.id)
                ocpus = shape_details.ocpus if shape_details and hasattr(shape_details, 'ocpus') else ""
                memory = shape_details.memory_in_gbs if shape_details and hasattr(shape_details, 'memory_in_gbs') else ""
                # Get boot volume size
                boot_volume_size = ""
                try:
                    boot_volumes = compute_client.list_boot_volume_attachments(compartment.id, instance.availability_domain, instance.id).data
                    if boot_volumes:
                        boot_volume_id = boot_volumes[0].boot_volume_id
                        boot_volume_size = get_boot_volume_size(blockstorage_client, boot_volume_id)
                except Exception:
                    boot_volume_size = "Unknown"
                # Get image name
                image_name = get_image_name(compute_client, instance.image_id) if hasattr(instance, 'image_id') else ""
                writer.writerow([
                    compartment.name, compartment.id, vcn_name, vcn_id, subnet_name, subnet_id,
                    instance.display_name, instance.id, ocpus, memory, boot_volume_size, image_name
                ])
    print(f"Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    main()
