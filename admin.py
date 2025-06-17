from database import create_user,init_db
init_db()
# مقدار id تلگرام خودت رو بذار جای عدد زیر
create_user(6033914166, "اسم شما", role="admin")
