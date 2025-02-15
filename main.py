import ImageNetTool


def main():
    while True:
        print("\n选择操作:")
        print("1. 上传图片")
        print("2. 下载图片")
        print("3. 退出")
        choice = input("请输入选项: ")

        if choice == '1':
            file_path = input("请输入要上传的图片路径: ")
            ImageNetTool.upload_image(file_path)
        elif choice == '2':
            filename = input("请输入要下载的文件名: ")
            save_path = input("请输入保存路径: ")
            ImageNetTool.download_image(filename, save_path)
        elif choice == '3':
            print("退出程序")
            break
        else:
            print("无效选项，请重新选择")

if __name__ == '__main__':
    main()