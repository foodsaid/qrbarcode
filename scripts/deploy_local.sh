#!/usr/bin/env bash

set -euo pipefail

IMAGE_REPO="${IMAGE_REPO:-qr-service}"
STABLE_TAG="${STABLE_TAG:-stable}"
CONTAINER_NAME="${CONTAINER_NAME:-qr-service}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
NETWORK_NAME="${NETWORK_NAME:-qrnetwork}"

usage() {
    cat <<'EOF'
Usage:
  ./scripts/deploy_local.sh deploy
  ./scripts/deploy_local.sh redeploy
  ./scripts/deploy_local.sh rollback <tag>
  ./scripts/deploy_local.sh status
  ./scripts/deploy_local.sh images
  ./scripts/deploy_local.sh cleanup-dangling

Environment variables:
  IMAGE_REPO     Docker image repository name (default: qr-service)
  STABLE_TAG     Stable tag used by compose (default: stable)
  NETWORK_NAME   External compose network name (default: qrnetwork)
EOF
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Error: docker command not found"
        exit 1
    fi
}

ensure_network() {
    if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
        echo "Creating docker network: ${NETWORK_NAME}"
        docker network create "${NETWORK_NAME}" >/dev/null
    fi
}

compose_up_with_tag() {
    local tag="$1"
    IMAGE_REPO="${IMAGE_REPO}" IMAGE_TAG="${tag}" docker compose -f "${COMPOSE_FILE}" up -d --no-build --force-recreate
}

deploy() {
    local release_tag
    release_tag="$(date +%Y%m%d-%H%M%S)"

    echo "Building ${IMAGE_REPO}:${release_tag}"
    docker build -t "${IMAGE_REPO}:${release_tag}" .

    echo "Tagging stable image ${IMAGE_REPO}:${STABLE_TAG}"
    docker tag "${IMAGE_REPO}:${release_tag}" "${IMAGE_REPO}:${STABLE_TAG}"

    ensure_network

    echo "Deploying container ${CONTAINER_NAME} with tag ${STABLE_TAG}"
    compose_up_with_tag "${STABLE_TAG}"

    echo "Release tag: ${release_tag}"
    # Keep only the latest 5 versioned images; remove older ones to prevent disk bloat
    docker images "${IMAGE_REPO}" --format '{{.Tag}}' \
        | grep -E '^[0-9]{8}-[0-9]{6}$' \
        | sort -r \
        | tail -n +6 \
        | xargs -r -I{} docker rmi "${IMAGE_REPO}:{}" 2>/dev/null || true
    status
}

redeploy() {
    ensure_network
    echo "Redeploying from stable image ${IMAGE_REPO}:${STABLE_TAG}"
    compose_up_with_tag "${STABLE_TAG}"
    status
}

rollback() {
    local tag="$1"

    if ! docker image inspect "${IMAGE_REPO}:${tag}" >/dev/null 2>&1; then
        echo "Error: image not found: ${IMAGE_REPO}:${tag}"
        exit 1
    fi

    echo "Switching stable tag to ${IMAGE_REPO}:${tag}"
    docker tag "${IMAGE_REPO}:${tag}" "${IMAGE_REPO}:${STABLE_TAG}"

    ensure_network
    echo "Redeploying rollback target ${tag}"
    compose_up_with_tag "${STABLE_TAG}"
    status
}

status() {
    echo "=== Container status ==="
    docker ps --filter "name=^/${CONTAINER_NAME}$" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
    echo ""
    echo "=== Stable image ==="
    docker image inspect "${IMAGE_REPO}:${STABLE_TAG}" --format 'ID={{.Id}} Created={{.Created}}' 2>/dev/null || echo "Not found: ${IMAGE_REPO}:${STABLE_TAG}"
}

images() {
    docker images "${IMAGE_REPO}" --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}'
}

cleanup_dangling() {
    echo "Removing dangling images only"
    docker image prune -f
}

main() {
    require_docker

    local cmd="${1:-}"
    case "${cmd}" in
        deploy)
            deploy
            ;;
        redeploy)
            redeploy
            ;;
        rollback)
            if [ "${2:-}" = "" ]; then
                echo "Error: rollback requires a tag"
                usage
                exit 1
            fi
            rollback "$2"
            ;;
        status)
            status
            ;;
        images)
            images
            ;;
        cleanup-dangling)
            cleanup_dangling
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
