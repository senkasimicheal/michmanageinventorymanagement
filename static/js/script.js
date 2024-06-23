$(document).ready(function(){

    $('#login').click(function(){
        $('.login-form').addClass('popup');
        $('.signup-form').removeClass('popup');
        $('.tanant-login-form').removeClass('popup');
        $('.tenant-signup-form').removeClass('popup');
    });

    $('.login-form form .fa-times').click(function(){
        $('.login-form').removeClass('popup');
    });

    $('#signup').click(function(){
        $('.signup-form').addClass('popup');
        $('.login-form').removeClass('popup');
        $('.tanant-login-form').removeClass('popup');
        $('.tenant-signup-form').removeClass('popup');
    });

    $('.signup-form form .fa-times').click(function(){
        $('.signup-form').removeClass('popup');
    });

    $('#tenant-login').click(function(){
        $('.tanant-login-form').addClass('popup');
        $('.login-form').removeClass('popup');
        $('.signup-form').removeClass('popup');
        $('.tenant-signup-form').removeClass('popup');
    });

    $('.tanant-login-form form .fa-times').click(function(){
        $('.tanant-login-form').removeClass('popup');
    });

    $('#tenant-signup').click(function(){
        $('.tenant-signup-form').addClass('popup');
        $('.login-form').removeClass('popup');
        $('.signup-form').removeClass('popup');
        $('.tanant-login-form').removeClass('popup');
    });

    $('.tenant-signup-form form .fa-times').click(function(){
        $('.tenant-signup-form').removeClass('popup');
    });

    $('#add-property').click(function(){
        $('.property-form').addClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
    });

    $('.property-form form .fa-times').click(function(){
        $('.property-form').removeClass('popup');
    });

    $('#add-tenant').click(function(){
        $('.tenant-form').addClass('popup');
        $('.property-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
    });

    $('.tenant-form form .fa-times').click(function(){
        $('.tenant-form').removeClass('popup');
    });

    $('#export').click(function(){
        $('.export-form').addClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
    });

    $('.export-form form .fa-times').click(function(){
        $('.export-form').removeClass('popup');
    });

    $('#new-stock').click(function(){
        $('.new-stock-form').addClass('popup');
        $('.export-form').removeClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
        $('.inhouse-use-form').removeClass('popup');
    });

    $('.new-stock-form form .fa-times').click(function(){
        $('.new-stock-form').removeClass('popup');
    });

    $('#update-new-stock').click(function(){
        $('.update-new-stock-form').addClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
        $('.inhouse-use-form').removeClass('popup');
    });

    $('.update-new-stock-form form .fa-times').click(function(){
        $('.update-new-stock-form').removeClass('popup');
    });

    $('#update-sale').click(function(){
        $('.update-sales-form').addClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
        $('.inhouse-use-form').removeClass('popup');
    });

    $('.update-sales-form form .fa-times').click(function(){
        $('.update-sales-form').removeClass('popup');
    });

    $('#inhouse').click(function(){
        $('.inhouse-updates-form').addClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
        $('.inhouse-use-form').removeClass('popup');
    });

    $('.inhouse-updates-form form .fa-times').click(function(){
        $('.inhouse-updates-form').removeClass('popup');
    });

    $('#inhouse-use').click(function(){
        $('.inhouse-use-form').addClass('popup');
        $('.inhouse-updates-form').removeClass('popup');
        $('.update-sales-form').removeClass('popup');
        $('.update-new-stock-form').removeClass('popup');
        $('.new-stock-form').removeClass('popup');
        $('.export-form').removeClass('popup');
        $('.property-form').removeClass('popup');
        $('.tenant-form').removeClass('popup');
    });

    $('.inhouse-use-form form .fa-times').click(function(){
        $('.inhouse-use-form').removeClass('popup');
    });
});