function studentController($scope,$http) {
var url="data.txt";
   $http.get("http://127.0.0.1:8000/students").success( function(response) {
        $scope.students = response; 
    });
}