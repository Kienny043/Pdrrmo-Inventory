"""Stock-integrity service functions (spec audit decisions 2.1 / 2.12).

The single place an item's quantity ever changes after creation. Both
``POST /api/movements/add/`` and request approval call
``apply_stock_movement`` so a ``StockMovement`` row (the audit trail) is
written every time, and the insufficient-stock check always runs before
any write.
"""

import time

from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from .models import InventoryItem, StockMovement

# Transient write-lock contention retry. Real on SQLite (dev), where a second
# concurrent writer can raise "database is locked" rather than waiting; a
# no-op in practice on PostgreSQL (prod), where select_for_update() below
# makes the second writer block on the row instead of erroring.
_LOCK_RETRIES = 6
_LOCK_BACKOFF = 0.05


class InsufficientStock(Exception):
    """An OUT movement would take an item below zero (or lost a concurrent race)."""

    def __init__(self, item, requested, available):
        self.item = item
        self.requested = requested
        self.available = available
        super().__init__(
            f"Only {available} of '{item.name}' on hand; {requested} requested."
        )


def apply_stock_movement(item, quantity, movement_type, *, performed_by, note=""):
    """Adjust stock + record a movement, retrying transient write-lock errors.

    The real work is in ``_apply_stock_movement_once`` (one atomic attempt).
    ``InsufficientStock`` is a genuine answer and is never retried.
    """
    last_exc = None
    for attempt in range(_LOCK_RETRIES):
        try:
            return _apply_stock_movement_once(
                item, quantity, movement_type, performed_by=performed_by, note=note
            )
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            time.sleep(_LOCK_BACKOFF * (attempt + 1))
    raise last_exc


@transaction.atomic
def _apply_stock_movement_once(item, quantity, movement_type, *, performed_by, note=""):
    """One atomic attempt: adjust ``item.quantity`` and record a ``StockMovement``.

    - Locks the item row with ``select_for_update()`` — real serialization on
      PostgreSQL (prod); a no-op on SQLite (local dev), where the conditional
      ``F()`` UPDATE below is the portable integrity guarantee.
    - For an OUT movement, checks the current quantity *before* any write; on
      failure raises ``InsufficientStock`` and nothing is written — no
      quantity change, no ``StockMovement`` row.
    - Adjusts quantity with a single conditional ``UPDATE ... WHERE
      quantity >= n``; if it touches zero rows a concurrent caller drew the
      stock down first, so this one also raises ``InsufficientStock``.
    - Creates and returns the ``StockMovement`` row.
    """
    is_out = movement_type == StockMovement.MovementType.OUT
    locked = InventoryItem.objects.select_for_update().get(pk=item.pk)

    if is_out and locked.quantity < quantity:
        raise InsufficientStock(locked, quantity, locked.quantity)

    rows = InventoryItem.objects.filter(pk=locked.pk)
    if is_out:
        rows = rows.filter(quantity__gte=quantity)
    updated = rows.update(
        quantity=F("quantity") + (-quantity if is_out else quantity),
        updated_at=timezone.now(),
    )
    if updated == 0:
        # Lost the race between the check above and this UPDATE.
        locked.refresh_from_db(fields=["quantity"])
        raise InsufficientStock(locked, quantity, locked.quantity)

    locked.refresh_from_db(fields=["quantity", "updated_at"])
    return StockMovement.objects.create(
        item=locked,
        quantity=quantity,
        movement_type=movement_type,
        performed_by=performed_by,
        note=note,
    )
