# Clean UP

1. Run `docker-compose down --volumes` in the following folders
    - oaken-spirits/src/production/analytics/airbyte
    - oaken-spirits/src/production/docker
1. Delete local repository
1. Delete `.json` file for service account.

>[!WARNING]
>This will delete all volumes, even those not associated with this project.

1. If you want to clean up all volumes on your docker system `docker volume prune --force`
