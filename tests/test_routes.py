######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from urllib.parse import quote_plus
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

# DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///../db/test.db')
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')

    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

        #
        # Uncomment this code once READ is implemented
        #

        # Check that the location header was correct
        response = self.client.get(location)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_get_product(self):
        """Test reading a product"""
        product_for_test = self._create_products(1)[0]

        response = self.client.get(f"{BASE_URL}/{product_for_test.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["id"], product_for_test.id)
        self.assertEqual(data["name"], product_for_test.name)

    def test_get_product_not_found(self):
        """It should response error 404 when id was not found"""
        fake_id = "99999"
        response = self.client.get(f"{BASE_URL}/{fake_id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_product(self):
        """It should update a product"""
        product = ProductFactory()
        new_data = product.serialize()
        response = self.client.post(BASE_URL, json=new_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        update_product = response.get_json()
        update_product["description"] = "test"
        id_to_update = update_product["id"]
        response = self.client.put(f"{BASE_URL}/{id_to_update}", json=update_product)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_product = response.get_json()
        self.assertEqual(updated_product["description"], "test")

    def test_update_not_id_exists_product(self):
        """It should update a product"""
        product = ProductFactory()
        new_data = product.serialize()
        id_to_update = "9999999999999"
        response = self.client.put(f"{BASE_URL}/{id_to_update}", json=new_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_product(self):
        """It should delete a product"""
        product_for_test = self._create_products(1)[0]
        response = self.client.get(f"{BASE_URL}/{product_for_test.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f"{BASE_URL}/{product_for_test.id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_all(self):
        """It should get all products"""
        products_list_for_test = self._create_products(10)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), len(products_list_for_test))

    def test_query_by_name(self):
        """It should get Products filtered by name"""
        products = self._create_products(10)
        filter_name = products[0].name
        filter_count = len([product for product in products if product.name == filter_name])
        response = self.client.get(BASE_URL, query_string=f"name={quote_plus(filter_name)}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), filter_count)
        for product in data:
            self.assertEqual(product["name"], filter_name)

    def test_query_by_category(self):
        """It should get Products filtered by category"""
        products = self._create_products(10)
        filter_param = products[0].category
        logging.debug("Search by category %s", filter_param.name)
        filter_count = len([product for product in products if product.category == filter_param])
        response = self.client.get(BASE_URL, query_string=f"category={filter_param.name}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), filter_count)
        for product in data:
            self.assertEqual(product["category"], filter_param.name)

    def test_query_by_availability(self):
        """It should get Products filtered by availability"""
        products = self._create_products(10)
        filter_param = products[0].available
        filter_count = len([product for product in products if product.available == filter_param])
        response = self.client.get(BASE_URL, query_string=f"available={filter_param}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), filter_count)
        for product in data:
            self.assertEqual(product["available"], filter_param)

    ######################################################################
    # Utility functions
    ######################################################################
    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        # logging.debug("data = %s", data)
        return len(data)
