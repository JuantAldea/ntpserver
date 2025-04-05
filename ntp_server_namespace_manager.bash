#!/bin/bash

# Script to run the Python NTP server (ntpserver.py) in a network namespace
# Author: Juan Antonio

set -e

BRIDGE="br0"
PREFIX="py_ntp_ns"
NTP_SERVER_SCRIPT="./ntpserver.py"
TMP_DIR="/tmp"

# Default values
INSTANCE="1"
SUBNET_BASE="192.168.100"
TIME_OFFSET="0"
NTP_STRATUM="2"
LEAP="0"
START_INSTANCE="1"
END_INSTANCE="1"

show_help() {
    cat <<EOF
Usage: $0 <action> [options]

Actions:
  create            - Create a new Python NTP server namespace
  batch             - Create multiple NTP server namespaces (range of instances)
  delete            - Delete the specified Python NTP namespace
  logs              - Show logs for the NTP server in the specified namespace
  list              - List all Python NTP namespaces
  cleanup           - Remove all Python NTP namespaces and resources
  help              - Show this help message

Options:
  -i, --instance ID   Instance number (default: 1)
  -s, --subnet BASE   Subnet base (default: 192.168.100)
  -o, --offset SEC    Time offset in seconds (default: 0)
  -t, --stratum NUM   NTP stratum level (default: 2)
  -l, --leap FLAG     Leap second flag (default: 0)

Batch mode options:
  --start N           Starting instance number (default: 1)
  --end N             Ending instance number (default: 1)

Examples:
  $0 create -i 1                         - Create namespace py_ntp_ns_1 with IP 192.168.100.1
  $0 create -i 2 -s 10.0.0 -o 3600 -t 1  - Create namespace with a 1-hour time offset and stratum 1
  $0 batch --start 1 --end 5 -s 10.0.0   - Create 5 namespaces with IPs 10.0.0.1 through 10.0.0.5
  $0 delete -i 1                         - Delete namespace py_ntp_ns_1
  $0 logs -i 1                           - Show logs for the server in namespace py_ntp_ns_1
  $0 cleanup                             - Remove all Python NTP namespaces
EOF
}

# Show help if no arguments provided
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

parse_args() {
    # Main command (first argument)
    ACTION="$1"
    shift

    if [[ "$ACTION" == "help" || "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
        show_help
        exit 0
    fi

    if [[ "$ACTION" == "list" || "$ACTION" == "cleanup" ]]; then
        return
    fi

    local options
    if ! options=$(getopt -o i:s:o:t:l: --long instance:,subnet:,offset:,stratum:,leap:,start:,end: -n 'py2_ntp.bash' -- "$@"); then
        echo "Invalid options provided"
        show_help
        exit 1
    fi

    eval set -- "$options"

    while true; do
        case "$1" in
        -i | --instance)
            INSTANCE="$2"
            if ! [[ "$INSTANCE" =~ ^[0-9]+$ ]]; then
                echo "Error: Instance must be an integer."
                exit 1
            fi
            shift 2
            ;;
        -s | --subnet)
            SUBNET_BASE="$2"
            shift 2
            ;;
        -o | --offset)
            TIME_OFFSET="$2"
            if ! [[ "$TIME_OFFSET" =~ ^-?[0-9]+$ ]]; then
                echo "Error: Offset must be an integer."
                exit 1
            fi
            shift 2
            ;;
        -t | --stratum)
            NTP_STRATUM="$2"
            if ! [[ "$NTP_STRATUM" =~ ^[0-9]+$ ]]; then
                echo "Error: Stratum must be an integer."
                exit 1
            fi
            shift 2
            ;;
        -l | --leap)
            LEAP="$2"
            if ! [[ "$LEAP" =~ ^[0-3]$ ]]; then
                echo "Error: Leap status must be [0, 3]."
                exit 1
            fi
            shift 2
            ;;
        --start)
            START_INSTANCE="$2"
            if ! [[ "$START_INSTANCE" =~ ^[0-9]+$ ]]; then
                echo "Error: Start instance must be an integer."
                exit 1
            fi
            shift 2
            ;;
        --end)
            END_INSTANCE="$2"
            if ! [[ "$END_INSTANCE" =~ ^[0-9]+$ ]]; then
                echo "Error: End instance must be an integer."
                exit 1
            fi
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Internal error!"
            exit 1
            ;;
        esac
    done
}

get_instance_directory() {
    local instance="$1"
    local instance_dir="${TMP_DIR}/${PREFIX}_$instance"
    echo "$instance_dir"
}

create_ntp_namespace() {
    local instance="$1"
    local subnet_base="$2"
    local stratum="$3"
    local leap="$4"
    local offset="$5"
    local host_ip="$subnet_base.254"
    local ip_ns="$subnet_base.${instance}"
    local veth_host="veth${instance}_host"
    local veth_ns="veth${instance}_ns"
    local namespace="${PREFIX}_$instance"
    local instance_dir=$(get_instance_directory "$instance")
    local log_file="$instance_dir/server.log"

    echo "Creating namespace: $namespace with IP: $ip_ns"

    if ip netns list | grep -q "$namespace"; then
        echo "Error: Namespace $namespace already exists"
        return 1
    fi

    if [[ ! -f "$NTP_SERVER_SCRIPT" ]]; then
        echo "Error: Python NTP server script not found at $NTP_SERVER_SCRIPT"
        return 1
    fi

    chmod +x "$NTP_SERVER_SCRIPT"
    mkdir -p "$instance_dir"

    if ! ip link show "$BRIDGE" &>/dev/null; then
        echo "Creating bridge $BRIDGE"
        ip link add name "$BRIDGE" type bridge
        ip addr add "$host_ip/24" dev "$BRIDGE"
        ip link set "$BRIDGE" up
        sysctl -w net.ipv4.ip_forward=1 >/dev/null
    fi

    echo "Creating namespace: $namespace and veth pair: $veth_host <-> $veth_ns"

    ip netns add "$namespace"

    ip link add "$veth_host" type veth peer name "$veth_ns"
    ip link set "$veth_ns" netns "$namespace"

    ip link set "$veth_host" master "$BRIDGE"

    ip netns exec "$namespace" ip addr add "$ip_ns/24" dev "$veth_ns"

    ip link set "$veth_host" up
    ip netns exec "$namespace" ip link set "$veth_ns" up
    ip netns exec "$namespace" ip link set lo up

    ip netns exec "$namespace" ip route add default via "$host_ip" || true

    echo "Starting Python NTP server in namespace $namespace"
    echo "IP: $ip_ns, Time offset: $offset seconds, Stratum: $stratum, Leap: $leap"

    ip netns exec "$namespace" python3 "$NTP_SERVER_SCRIPT" \
        --ip "$ip_ns" \
        --offset "$offset" \
        --stratum "$stratum" \
        --leap "$leap" \
        --log_level DEBUG >"$log_file" 2>&1 &

    sleep 0.5
    PID=$(ip netns pids "$namespace" | grep -v "^$" | head -n 1) || true
    if [[ -z "$PID" ]]; then
        echo "Error: Failed to start Python NTP server for instance $instance"
        cat "$log_file"
        return 1
    fi

    echo "Python NTP server started successfully with PID $PID"
    echo "Namespace $namespace created with IP $ip_ns and running Python NTP server."
    return 0
}

delete_namespace() {
    set +e
    local instance="$1"
    local namespace="${PREFIX}_$instance"
    echo "Deleting namespace: $namespace"
    PID=$(ip netns pids "$namespace" 2>/dev/null | grep -v "^$" | head -n 1) || true
    if [[ -n "$PID" ]]; then
        echo "Stopping Python NTP server with PID $PID in namespace $namespace"
        nsenter --target "$PID" --pid -- kill -TERM "$PID" || true
    fi

    ip netns del "$namespace" || true

    ns_dir=$(get_instance_directory "$instance")
    echo "Deleting temporary directory: $ns_dir"
    rm -rf "$ns_dir"
    set -e
    echo "Namespace $namespace deleted."
}

get_logs() {
    local instance="$1"
    local namespace="${PREFIX}_$instance"
    local instance_dir=$(get_instance_directory "$instance")
    local log_file="$instance_dir/server.log"

    if ! ip netns list | grep -q "$namespace"; then
        echo "Error: Namespace $namespace does not exist"
        exit 1
    fi

    echo "Showing logs for NTP server in namespace: $instance"

    PID=$(ip netns pids "$namespace" | head -n 1)
    echo "PID: $PID"
    if [[ -n "$PID" ]]; then
        echo "Found Python process with PID $PID in namespace $namespace"
        echo "Process information:"
        nsenter --target "$PID" --pid -- ps -p "$PID" -f

        if [[ -f "$log_file" ]]; then
            printf '\nServer log:'
            cat "$log_file"
        else
            echo -e "\nNo log file found at $log_file"
        fi
    else
        echo "No Python NTP server process found in namespace $namespace"
    fi

}

# Check for root privileges
if [[ "$EUID" -ne 0 ]]; then
    echo "Error: This script must be run as root."
    exit 1
fi

# Parse command line arguments
parse_args "$@"

if [[ "$ACTION" == "list" ]]; then
    echo "NTP namespaces:"
    ip netns list | grep "$PREFIX"
    exit 0
fi

if [[ "$ACTION" == "delete" ]]; then
    delete_namespace "$INSTANCE"
    exit 0
fi

if [[ "$ACTION" == "logs" ]]; then
    get_logs "$INSTANCE"
    exit 0
fi

if [[ "$ACTION" == "cleanup" ]]; then
    echo "Cleaning up all Python2 NTP namespaces and resources"
    for ns in $(ip netns list | grep "${PREFIX}_" | awk '{print $1}'); do
        instance=${ns//${PREFIX}_/}
        delete_namespace "$instance"
    done

    if ip link show "$BRIDGE" &>/dev/null; then
        echo "Deleting bridge: $BRIDGE"
        ip link set "$BRIDGE" down || true
        ip link del "$BRIDGE" || true
    fi

    echo "Cleaning up temporary directories"
    rm -rf "${TMP_DIR}/${PREFIX}_*"

    echo "All NTP namespaces and resources have been cleaned up."
    exit 0
fi

if [[ "$ACTION" == "batch" ]]; then
    echo "Creating multiple NTP server namespaces from instance $START_INSTANCE to $END_INSTANCE"
    echo "Using subnet $SUBNET_BASE, time offset $TIME_OFFSET seconds, stratum $NTP_STRATUM"

    success_count=0
    fail_count=0
    set +e
    for i in $(seq "$START_INSTANCE" "$END_INSTANCE"); do
        echo "=== Creating instance $i ==="

        if create_ntp_namespace "$i" "$SUBNET_BASE" "$NTP_STRATUM" "$LEAP" "$TIME_OFFSET"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
        echo ""
    done
    set -e

    echo "Batch creation complete: $success_count instances created successfully, $fail_count failures."
    echo "Use '$0 list' to see all namespaces."
    echo "Use '$0 logs -i <instance>' to view logs for a specific server."
    exit 0
fi

if [[ "$ACTION" == "create" ]]; then
    create_ntp_namespace "$INSTANCE" "$SUBNET_BASE" "$NTP_STRATUM" "$LEAP" "$TIME_OFFSET"
    echo "Use '$0 logs -i $INSTANCE' to view server logs."
    exit 0
fi

echo "Error: Invalid action '$ACTION'"
echo "Run '$0' or '$0 help' to see available commands and options"
exit 1
