\set ON_ERROR_STOP on

BEGIN;

LOCK TABLE tickets, categories, users
IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE tickets
    SET
        department_id = 3,
        assigned_to = NULL,
        status = 'under_review',
        updated_at = NOW()
    WHERE id = 6
      AND category_id = 1
      AND department_id = 1
      AND assigned_to = 3
      AND status = 'in_progress'
      AND is_deleted IS FALSE;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;

    IF affected_rows <> 1 THEN
        RAISE EXCEPTION
            'Ticket 6 does not match the expected original state';
    END IF;

    UPDATE tickets
    SET
        department_id = 3,
        updated_at = NOW()
    WHERE id = 7
      AND category_id = 1
      AND department_id = 1
      AND assigned_to IS NULL
      AND status = 'open'
      AND is_deleted IS TRUE;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;

    IF affected_rows <> 1 THEN
        RAISE EXCEPTION
            'Ticket 7 does not match the expected original state';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM tickets t
        JOIN categories c ON c.id = t.category_id
        WHERE t.department_id <> c.department_id
    ) THEN
        RAISE EXCEPTION
            'Category-department inconsistencies remain';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM tickets t
        JOIN users u ON u.id = t.assigned_to
        WHERE t.department_id <> u.department_id
    ) THEN
        RAISE EXCEPTION
            'Agent-department inconsistencies remain';
    END IF;

    RAISE NOTICE 'Data repair validation passed';
END;
$$;

SELECT
    id,
    category_id,
    department_id,
    assigned_to,
    status,
    is_deleted
FROM tickets
WHERE id IN (6, 7)
ORDER BY id;

COMMIT;