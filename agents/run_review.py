
from agents.crew import PhoneReviewCrew


def main():
    question = input("Enter your phone review question: ")

    crew = PhoneReviewCrew()

    result = crew.run(question)

    print("\n========== GENERATED REVIEW ==========\n")
    print(result)


if __name__ == "__main__":
    main()
