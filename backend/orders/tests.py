import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from delivery.models import CourierProfile, DeliveryTask
from orders.models import Order, OrderItem
from shops.models import CatalogItem, Shop


class BazaarDocumentedScenarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.client_user = user_model.objects.create_user(
            username="client",
            email="client@example.com",
            password="secret123",
            role=user_model.Roles.CLIENT,
            display_name="Client",
            phone="+70000000001",
        )
        cls.other_client = user_model.objects.create_user(
            username="other-client",
            email="other@example.com",
            password="secret123",
            role=user_model.Roles.CLIENT,
        )
        cls.shop_user = user_model.objects.create_user(
            username="shop-owner",
            password="secret123",
            role=user_model.Roles.SHOP,
        )
        cls.courier_user = user_model.objects.create_user(
            username="courier",
            password="secret123",
            role=user_model.Roles.COURIER,
        )
        cls.other_courier_user = user_model.objects.create_user(
            username="other-courier",
            password="secret123",
            role=user_model.Roles.COURIER,
        )
        cls.admin_user = user_model.objects.create_user(
            username="admin",
            password="secret123",
            role=user_model.Roles.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        cls.courier_profile = CourierProfile.objects.create(user=cls.courier_user)
        CourierProfile.objects.create(user=cls.other_courier_user)

        cls.shop = Shop.objects.create(
            owner=cls.shop_user,
            name="Fresh Market",
            address="Market street, 1",
            description="Daily products",
        )
        cls.item = CatalogItem.objects.create(
            shop=cls.shop,
            name="Milk",
            description="1 liter",
            price=Decimal("120.50"),
            is_available=True,
        )

    def post_json(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def patch_json(self, path, payload):
        return self.client.patch(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def create_order(self, quantity=1):
        self.client.force_login(self.client_user)
        response = self.post_json(
            "/api/orders/",
            {
                "shop_id": self.shop.id,
                "delivery_address": "Client street, 10",
                "items": [
                    {
                        "catalog_item_id": self.item.id,
                        "quantity": quantity,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Order.objects.get(pk=response.json()["id"])

    def test_case_01_registers_new_user(self):
        response = self.post_json(
            "/api/auth/register/",
            {
                "username": "new-client",
                "email": "new-client@example.com",
                "password": "secret123",
                "password2": "secret123",
                "display_name": "New Client",
                "phone": "+70000000002",
            },
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["role"], get_user_model().Roles.CLIENT)
        self.assertTrue(get_user_model().objects.filter(username="new-client").exists())

    def test_case_02_logs_in_with_valid_credentials(self):
        response = self.post_json(
            "/api/auth/login/",
            {"username": "client", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "client")
        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200, me_response.content)

    def test_case_03_rejects_invalid_login_credentials(self):
        response = self.post_json(
            "/api/auth/login/",
            {"username": "client", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.json()["detail"], "Invalid credentials")

    def test_case_04_shows_shop_catalog_with_prices_and_availability(self):
        shops_response = self.client.get("/api/shops/")
        catalog_response = self.client.get(f"/api/shops/{self.shop.id}/catalog/")

        self.assertEqual(shops_response.status_code, 200, shops_response.content)
        self.assertEqual(catalog_response.status_code, 200, catalog_response.content)
        self.assertEqual(shops_response.json()[0]["name"], self.shop.name)
        catalog_item = catalog_response.json()["catalog"][0]
        self.assertEqual(catalog_item["name"], self.item.name)
        self.assertEqual(catalog_item["price"], "120.50")
        self.assertTrue(catalog_item["is_available"])

    def test_case_05_reflects_cart_quantity_in_order_items_and_total(self):
        order = self.create_order(quantity=2)

        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order.total_price, Decimal("241.00"))

    def test_case_06_creates_order_with_valid_data(self):
        order = self.create_order(quantity=1)

        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.delivery_address, "Client street, 10")
        self.assertEqual(order.items.count(), 1)

    def test_case_07_does_not_create_order_from_empty_cart(self):
        self.client.force_login(self.client_user)
        response = self.post_json(
            "/api/orders/",
            {
                "shop_id": self.shop.id,
                "delivery_address": "Client street, 10",
                "items": [],
            },
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["detail"], "Items must be a non-empty list")

    def test_case_08_shows_current_order_status_to_client(self):
        order = self.create_order()
        self.client.force_login(self.shop_user)
        self.patch_json(
            f"/api/orders/{order.id}/status/",
            {"status": Order.Status.COOKING},
        )

        self.client.force_login(self.client_user)
        response = self.client.get(f"/api/orders/{order.id}/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Order.Status.COOKING)

    def test_case_09_partner_adds_and_updates_catalog_item(self):
        self.client.force_login(self.shop_user)
        create_response = self.post_json(
            f"/api/shops/{self.shop.id}/catalog/manage/",
            {
                "name": "Bread",
                "price": "55.00",
                "description": "Wheat bread",
                "is_available": True,
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)

        item_id = create_response.json()["id"]
        update_response = self.patch_json(
            f"/api/shops/{self.shop.id}/catalog/manage/{item_id}/",
            {"name": "Rye bread", "price": "60.00"},
        )

        self.assertEqual(update_response.status_code, 200, update_response.content)
        self.assertEqual(update_response.json()["name"], "Rye bread")
        self.assertEqual(update_response.json()["price"], "60.00")

    def test_case_10_partner_accepts_new_order(self):
        order = self.create_order()
        self.client.force_login(self.shop_user)
        response = self.patch_json(
            f"/api/orders/{order.id}/status/",
            {"status": Order.Status.COOKING},
        )

        self.assertEqual(response.status_code, 200, response.content)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COOKING)

    def test_case_11_courier_accepts_ready_delivery_task(self):
        order = self.create_order()
        self.client.force_login(self.shop_user)
        self.patch_json(
            f"/api/orders/{order.id}/status/",
            {"status": Order.Status.ON_DELIVERY},
        )
        task = DeliveryTask.objects.get(order=order)

        self.client.force_login(self.courier_user)
        offers_response = self.client.get("/api/delivery/offers/")
        assign_response = self.post_json(f"/api/delivery/offers/{task.id}/assign/", {})

        self.assertEqual(offers_response.status_code, 200, offers_response.content)
        self.assertEqual([offer["id"] for offer in offers_response.json()], [task.id])
        self.assertEqual(assign_response.status_code, 200, assign_response.content)

        task.refresh_from_db()
        self.assertEqual(task.courier, self.courier_profile)
        self.assertEqual(task.status, DeliveryTask.Status.ASSIGNED)

        self.client.force_login(self.other_courier_user)
        self.assertEqual(self.client.get("/api/delivery/offers/").json(), [])

    def test_case_12_courier_completes_delivery(self):
        order = self.create_order()
        task = DeliveryTask.objects.create(
            order=order,
            courier=self.courier_profile,
            status=DeliveryTask.Status.ASSIGNED,
        )

        self.client.force_login(self.courier_user)
        response = self.patch_json(
            f"/api/delivery/tasks/{task.id}/status/",
            {"status": DeliveryTask.Status.DONE},
        )

        self.assertEqual(response.status_code, 200, response.content)
        task.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(task.status, DeliveryTask.Status.DONE)
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_case_13_payment_module_is_not_implemented(self):
        order = self.create_order()
        response = self.post_json(f"/api/orders/{order.id}/pay/", {})

        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    def test_case_14_order_appeal_module_is_not_implemented(self):
        order = self.create_order()
        order.status = Order.Status.DELIVERED
        order.save()

        response = self.post_json(
            f"/api/orders/{order.id}/appeals/",
            {"reason": "Need refund"},
        )

        self.assertEqual(response.status_code, 404)
