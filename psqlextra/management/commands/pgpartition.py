import sys

from typing import Optional

import colorama

from ansimarkup import ansiprint, ansistring
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from psqlextra.partitioning import PostgresPartitioningError


class Command(BaseCommand):
    """Create new partitions and delete old ones according to the configured
    partitioning strategies."""

    help = "Create new partitions and delete old ones using the configured partitioning manager. The PSQLEXTRA_PARTITIONING_MANAGER setting must be configured."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry",
            "-d",
            action="store_true",
            help="When specified, no partition will be created/deleted. Just a simulation.",
            required=False,
            default=False,
        )

        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Answer yes to all questions. WARNING: You will not be asked before deleting a partition.",
            required=False,
            default=False,
        )

        parser.add_argument(
            "--using",
            "-u",
            help="Name of the database connection to use.",
            default="default",
        )

        parser.add_argument(
            "--no-create",
            action="store_true",
            help="Do not create partitions.",
            required=False,
            default=False,
        )

        parser.add_argument(
            "--no-delete",
            action="store_true",
            help="Do not delete partitions.",
            required=False,
            default=False,
        )

    def handle(
        self,
        dry: bool,
        yes: bool,
        using: Optional[str],
        no_create: bool,
        no_delete: bool,
    ):
        # disable coloring if no terminal is attached
        if not sys.stdout.isatty():
            colorama.init(strip=True)

        partitioning_manager = self._partitioning_manager()

        plans = partitioning_manager.apply(
            dry_run=True, no_create=no_create, no_delete=no_delete, using=using
        )

        for plan in plans:
            plan.print()
            print("")

        create_count = sum([len(plan.created_partitions) for plan in plans])
        delete_count = sum([len(plan.deleted_partitions) for plan in plans])
        if create_count == 0 and delete_count == 0:
            ansiprint("<b><white>Nothing to be done.</white></b>")
            return

        ansiprint(
            f"<b><red>{delete_count} partitions will be deleted</red></b>"
        )
        ansiprint(
            f"<b><green>{create_count} partitions will be created</green></b>"
        )

        if dry:
            return

        if not yes:
            sys.stdout.write(
                ansistring(
                    "<b><white>Do you want to proceed? (y/N) </white></b>"
                )
            )

            if not self._ask_for_confirmation():
                ansiprint("<b><white>Operation aborted.</white></b>")
                return

        partitioning_manager.apply(
            dry_run=False, no_create=no_create, no_delete=no_delete, using=using
        )
        ansiprint("<b><white>Operations applied.</white></b>")

    @staticmethod
    def _ask_for_confirmation() -> bool:
        answer = input("").lower()
        if not answer:
            return False

        if answer[0] == "y" or answer == "yes":
            return True

        return False

    @staticmethod
    def _partitioning_manager():
        partitioning_manager = getattr(
            settings, "PSQLEXTRA_PARTITIONING_MANAGER"
        )
        if not partitioning_manager:
            raise PostgresPartitioningError(
                "You must configure the PSQLEXTRA_PARTITIONING_MANAGER setting "
                "for automatic partitioning to work."
            )

        if isinstance(partitioning_manager, str):
            partitioning_manager = import_string(partitioning_manager)

        return partitioning_manager
