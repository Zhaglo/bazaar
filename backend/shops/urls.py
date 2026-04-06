from django.urls import path
from . import views

urlpatterns = [
    path('shops/', views.shop_list, name='shop_list'),
    path('shops/my/', views.my_shops, name='my_shops'),
    path('shops/<int:shop_id>/catalog/', views.shop_catalog, name='shop_menu'),
    path('shops/apply/', views.shop_application_create, name='shop_apply'),

    path(
        'shops/<int:shop_id>/catalog/manage/',
        views.shop_catalog_manage,
        name='shop_catalog_manage',
    ),
    path(
        'shops/<int:shop_id>/catalog/manage/<int:item_id>/',
        views.shop_catalog_item_manage,
        name='shop_catalog_item_manage',
    ),

    path(
        'shops/<int:shop_id>/sections/',
        views.shop_sections_manage,
        name='shop_sections_manage'
    ),
    path(
        'shops/<int:shop_id>/sections/<int:section_id>/',
        views.shop_section_item_manage,
        name='shop_section_item_manage'
    ),

    path('shops/<int:shop_id>/stats/', views.shop_stats, name='shop_stats'),
]
