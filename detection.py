import docker
import subprocess
def load_image(tar_path):
    with open(tar_path, "rb") as f:
        images = client.images.load(f.read())
    image = images[0]
    print(f"Loaded image: {image.id}, tags: {image.tags}")
    return image

def run_container(image, container_name=None, command=None):
    container = client.containers.run(
        image=image.id,
        name=container_name,
        command=command,
        detach=True
    )
    print(f"Container started: {container.name} ({container.id})")
    return container

def monitor_loop(container, handler_script):
    print(f"Monitoring container {container.name} events ...")
    event_stream = client.events(decode=True)

    for event in event_stream:
        if event.get("Type") != "container":
            continue

        actor_attrs = event.get("Actor", {}).get("Attributes", {})
        name = actor_attrs.get("name")
        if name != container.name:
            continue

        event_status = event.get("status")
        if event_status in ["die","kill"]:
            exit_code = event.get("Actor", {}).get("Attributes", {}).get("exitCode", "unknown")
            if event_status == "die":
                if exit_code != "unknown" and int(exit_code) != 0:
                    print(f"Calling handler script: {handler_script}")
                    subprocess.run(["python3"] + handler_script)
                    print("Exiting monitoring process.")
                    break
            else:
                print(f"Calling handler script: {handler_script}")
                subprocess.run(["python3", handler_script])
                print("Exiting monitoring process.")
                break

client = docker.from_env()
if __name__ == "__main__":
    tar_file = "/home/breeze/python.tar"
    container_name = "updated_app"
    handler_script = ["substitute.py", "inc", "patch"]

    image = load_image(tar_file)

    container = run_container(image, container_name=container_name)

    monitor_loop(container, handler_script)