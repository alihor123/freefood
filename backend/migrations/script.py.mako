"""${message}"""

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Применяет изменение схемы."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Откатывает изменение схемы."""
    ${downgrades if downgrades else "pass"}
