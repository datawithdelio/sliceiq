# Endpoint Test Matrix (Day 11–12 Review)

Legend: auth = none | user | admin | bearer

| Method | Path | Auth | Success case | Failure case(s) | Test coverage |
| --- | --- | --- | --- | --- | --- |
| GET | /health | none | 200, status=ok | n/a | apps/backend/tests/test_health.py::test_health_endpoint |
| GET | /ping-redis | none | 200, redis connected (requires UPSTASH_REDIS_URL/REDIS_URL) | 500 when env missing | apps/backend/tests/test_review_phase.py::test_ping_redis_missing_env |
| GET | /protected/me | bearer | 200, returns sub as user_id | 401 missing/invalid token | apps/backend/tests/test_review_phase.py::test_protected_me_success; test_protected_me_unauthorized |
| POST | /orders/ | user | 200, creates order + stripe session | 500 when Stripe not configured; 422 bad payload | apps/backend/tests/test_orders.py::test_create_order; apps/backend/tests/test_review_phase.py::test_orders_create_missing_stripe; test_orders_create_bad_payload |
| POST | /orders/ | user | 200, repeat request creates new order (non-idempotent) | n/a | apps/backend/tests/test_review_phase.py::test_orders_create_retry_not_idempotent |
| GET | /orders/ | user | 200, list user orders | n/a | Existing coverage not added in Day 11–12 |
| GET | /orders/{order_id} | user | 200, owner or admin | 403 if not owner/admin; 404 if missing | apps/backend/tests/test_review_phase.py::test_orders_get_forbidden; test_orders_get_not_found |
| PATCH | /orders/{order_id}/status | admin | 200, status updated | 403 if not admin; 404 if missing | apps/backend/tests/test_orders.py::test_update_order_status_admin; apps/backend/tests/test_review_phase.py::test_orders_status_requires_admin |
| GET | /users/me | user | 200, profile | 401 if invalid token/user | apps/backend/tests/test_users.py::test_get_current_user_profile; apps/backend/tests/test_review_phase.py::test_users_me_unauthorized |
| PUT | /users/me | user | 200, updated profile | 401 if invalid token/user | apps/backend/tests/test_users.py::test_update_profile; apps/backend/tests/test_review_phase.py::test_users_me_unauthorized |
| GET | /products/ | none | 200, list products | n/a | apps/backend/tests/test_products.py::test_get_products_empty |
| GET | /products/{product_id} | none | 200, product returned | 404 if missing | apps/backend/tests/test_review_phase.py::test_products_crud; test_products_not_found |
| POST | /products/ | none | 201, product created | 422 bad payload | apps/backend/tests/test_review_phase.py::test_products_crud |
| PUT | /products/{product_id} | none | 200, product updated | 404 if missing | apps/backend/tests/test_review_phase.py::test_products_crud |
| DELETE | /products/{product_id} | none | 204, product deleted | 404 if missing | apps/backend/tests/test_review_phase.py::test_products_crud |
| GET | /ml/churn/{user_id} | admin | 200, churn scoring payload | 404 if model artifact missing | apps/backend/tests/test_review_phase.py::test_ml_churn_missing_model |

Notes:
- /ping-redis success path requires Redis; only negative path is asserted for CI determinism.
- /orders/ repeat create is documented as non-idempotent per current implementation.
- /ml/churn success path requires model artifact at CHURN_MODEL_PATH; v1 baseline does not include this binary.
