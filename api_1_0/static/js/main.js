$(function(){

    $("#btn").click(function(){
        $.ajax({
            url : "http://128.0.0.1:8000/add",
            type : "post",
            data : {"name":"Jane",
"classes":"grade7",
"location":"Berlin",}, 
            success:function(){
            }
        })
    })
})


