select
    StoreNumber,
    StoreName,
    Address,
    City,
    CountyName,
    State,
    ZipCode
from {{ source('oaken', 'customers') }}
